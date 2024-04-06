#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import base64

import cv2
import flet as ft
import numpy as np
from psd_tools import PSDImage

from clip_studio_paint_tool.csp_tool import CspTool


class CspPsdTool(object):

    def __init__(
        self,
        filepath,
    ):
        self.csp_psd_tool = None

        # 拡張子を判断しCSP、PSDいずれかのファイルをオープンする
        self.file_extention = None
        self.file_extention = os.path.splitext(filepath)[-1]
        if self.file_extention == '.clip':
            self.csp_psd_tool = CspTool(filepath)
        elif self.file_extention == '.psd':
            self.csp_psd_tool = PSDImage.open(filepath)
        else:
            print('Error : Unexpected File Extension')

    def get_layer_list(self):
        layer_list = []
        if self.csp_psd_tool is None:
            return layer_list

        # レイヤー情報を取得
        if self.file_extention == '.clip':
            temp_layer_list = self.csp_psd_tool.get_layer_list()
            for index, layer_data in enumerate(temp_layer_list):
                if index == 0:
                    continue
                layer_list.append({
                    'name': layer_data['layer_name'],
                    'data': layer_data,
                })
        elif self.file_extention == '.psd':
            temp_layer_list = self.csp_psd_tool.descendants()
            for layer_data in temp_layer_list:
                layer_list.append({
                    'name': layer_data.name,
                    'data': layer_data,
                })

        return layer_list

    def get_image(self, layer_data):
        cv_image = None

        # 画像を取得
        if self.file_extention == '.clip':
            _, _, cv_image = self.csp_psd_tool.get_raster_data(
                canvas_id=layer_data['canvas_id'],
                layer_id=layer_data['main_id'],
            )
        elif self.file_extention == '.psd':
            pil_image = layer_data.topil()
            if pil_image is not None:
                cv_image = np.array(pil_image, dtype=np.uint8)
                cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGBA2BGRA)

        return cv_image


class FletMain(object):

    def __init__(self, title=''):
        # Pageオブジェクト
        self.page = None
        self.title = title

        # GUIパーツ初期化
        self._initialize_gui_parts()

        # 画像オブジェクト保持用変数
        self.csp_psd_tool = None

    def start(self):
        ft.app(target=self._main)

    def _main(self, page: ft.Page):
        self.page = page
        self.page.title = self.title

        # オーバーレイ表示登録
        self.page.overlay.append(self.file_picker)

        # パーツ登録
        self.page.add(
            ft.Row([
                self.button_file_picker,
                self.select_file_text,
            ]))
        self.page.add(
            ft.Row([
                self.container_list_view,
                self.container_image,
            ]))

    def _initialize_gui_parts(self):
        # GUIパーツ：ファイル選択ボタン
        self.button_file_picker = ft.ElevatedButton(
            "Pick file",
            icon=ft.icons.UPLOAD_FILE,
            on_click=lambda _: self.file_picker.pick_files(
                allow_multiple=False,
                allowed_extensions=['clip', 'psd'],
            ),
        )

        # GUIパーツ：ファイルピッカー
        self.file_picker = ft.FilePicker(on_result=self._exec_file_picker)

        # GUIパーツ：選択ファイルテキスト
        self.select_file_text = ft.Text()

        # GUIパーツ：レイヤー名 リストビュー
        self.list_view = ft.ListView(
            expand=1,
            spacing=2,
            padding=10,
            auto_scroll=False,
            visible=True,
        )
        self.container_list_view = ft.Container(
            content=self.list_view,
            bgcolor="#F0F4FA",
            width=435,
            height=600,
            padding=5,
        )

        # GUIパーツ：インジケーター（処理中）
        self.activity_indicator = ft.Container(
            content=ft.CupertinoActivityIndicator(
                radius=50,
                color=ft.colors.BLUE,
                animating=True,
            ),
            bgcolor="#F0F4FA",
            width=800,
            height=600,
            padding=5,
            visible=False,  # 初期表示は非表示
        )

        # GUIパーツ：画像表示
        self.image = ft.Image(
            src_base64='',
            width=800,
            height=600,
            fit=ft.ImageFit.CONTAIN,
            visible=False,
        )
        self.container_image = ft.Stack([
            ft.Container(
                content=self.image,
                bgcolor="#F0F4FA",
                width=800,
                height=600,
                padding=5,
            ),
            self.activity_indicator,
        ])

        # GUIパーツ：アラートダイアログ
        alert_dialog_text = "以下の何れかのレイヤーです"
        alert_dialog_text += "\n・ラスターデータが存在しない"
        alert_dialog_text += "\n・グレースケール画像（未対応）"
        alert_dialog_text += "\n・モノクロ画像（未対応）"
        self.alert_dialog = ft.AlertDialog(title=ft.Text(alert_dialog_text))

    def _exec_file_picker(self, e: ft.FilePickerResultEvent):
        file_path = ''
        if e.files is not None:
            file_path = e.files[0].path
            # ファイルオープン
            self.csp_psd_tool = CspPsdTool(file_path)

        # 選択ファイル表示更新
        self.select_file_text.value = file_path
        self.select_file_text.update()

        # リストビューにレイヤー名のボタンを追加
        self.list_view.controls.clear()
        if self.csp_psd_tool is not None:
            # レイヤー情報取得
            layer_list = self.csp_psd_tool.get_layer_list()
            for layer_data in layer_list:
                button = ft.TextButton(
                    text=layer_data['name'],
                    on_click=self._button_clicked,
                    data=layer_data['data'],
                )
                self.list_view.controls.append(button)

        # リストビュー表示更新
        self.list_view.visible = True
        self.list_view.update()

    def _button_clicked(self, e):
        # 処理中インジケーターを表示
        self.image.visible = False
        self.image.update()
        self.activity_indicator.visible = True
        self.activity_indicator.update()

        # イベント情報からレイヤー情報を取得
        layer_data = e.control.data

        # 指定レイヤーの画像を取得
        cv_image = None
        if self.csp_psd_tool is not None:
            cv_image = self.csp_psd_tool.get_image(layer_data)

        if cv_image is not None:
            # 画像情報をbase64形式に変換
            _, imencode_image = cv2.imencode('.png', cv_image)
            base64_image = base64.b64encode(imencode_image)
            base64_image = base64_image.decode("ascii")

            # 画像表示更新
            self.image.src_base64 = base64_image
            self.image.visible = True
            self.image.update()
        else:
            # 画像が読み出せなかった場合はアラートを表示
            self.page.dialog = self.alert_dialog
            self.alert_dialog.open = True
            self.page.update()

        # 処理中インジケーター非表示
        self.activity_indicator.visible = False
        self.activity_indicator.update()


if __name__ == '__main__':
    flet_main = FletMain('CSP PSD Image Viewer')
    flet_main.start()
