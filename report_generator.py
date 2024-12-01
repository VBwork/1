from  datetime import datetime

from matplotlib import cm

from osgeo import gdal

from qgis.PyQt.QtWidgets import QAction

from qgis.gui import QgisInterface

from PyQt5.QtCore import QVariant

from PyQt5.QtGui import QColor

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
)

from qgis.analysis import (
    QgsZonalStatistics,
)

from qgis.core import (
    QgsField,
    QgsProject,
    QgsRaster,
    QgsLayerTreeModel,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsRasterShader,
    QgsColorRampShader,
    QgsSingleBandPseudoColorRenderer,
    QgsPointXY,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
)

from qgis.gui import (
    QgisInterface,
)

from qgis.PyQt.QtWidgets import (
    QAction,
    QFileDialog,
    QMessageBox,
)

from matplotlib.colors import (
    ListedColormap, 
    hex2color,
)

import matplotlib.pyplot as plt

import numpy as np

from scipy.stats import (
    norm,
)

import os

import pandas as pd

import geopandas as gpd

from .index_statistics import IndexStatistics

from PIL import Image

from scipy.ndimage import label

from osgeo import gdal


class NDVIReportGenerator:

    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface


    def get_action(self) -> QAction:
        action = QAction("NDVI Analysis report", self.iface.mainWindow())
        action.setObjectName(" ")
        action.setWhatsThis(" ")
        action.setStatusTip(" ")
        action.triggered.connect(self.run)

        return action


    def ndvi_choice_layers(self, raster_layers, vector_layers):
        dialog = QDialog()
        dialog.setWindowTitle("Вибір шарів")
        dialog.setFixedSize(300, 300)

        layout = QVBoxLayout()

        ndvi_combo = QComboBox()
        for layer in raster_layers:
            ndvi_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("NDVI:"))
        layout.addWidget(ndvi_combo)

        ndvi_histogram_button = QPushButton("Вибрати файл NDVI Histogram")
        selected_histogram_label = QLabel("Файл не вибрано")
        layout.addWidget(QLabel("NDVI Histogram:"))
        layout.addWidget(ndvi_histogram_button)
        layout.addWidget(selected_histogram_label)
        ndvi_histogram_button.clicked.connect(
            lambda: self.select_file(dialog, selected_histogram_label)
        )
        
        ndvi_color_scale_button = QPushButton("Вибрати файл NDVI color scale")
        selected_color_scale_label = QLabel("Файл не вибрано")
        layout.addWidget(QLabel("NDVI color scale:"))
        layout.addWidget(ndvi_color_scale_button)
        layout.addWidget(selected_color_scale_label)
        ndvi_color_scale_button.clicked.connect(
            lambda: self.select_file(dialog, selected_color_scale_label)
        )

        ndvi_jpg_button = QPushButton("Вибрати зображення індексу")
        selected_jpg_label = QLabel("Файл не вибрано")
        layout.addWidget(QLabel("Зображення індексу:"))
        layout.addWidget(ndvi_jpg_button)
        layout.addWidget(selected_jpg_label)
        ndvi_jpg_button.clicked.connect(
            lambda: self.select_file(dialog, selected_jpg_label)
        )

        vector_combo = QComboBox()
        for layer in vector_layers:
            vector_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("Vector:"))
        layout.addWidget(vector_combo)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)

        dialog.setLayout(layout)

        if dialog.exec_():
            return ndvi_combo.currentText(), selected_histogram_label.text(), selected_color_scale_label.text(), selected_jpg_label.text(), vector_combo.currentText()
        return None
    

    def select_file(self, dialog, label):
        file_name, _ = QFileDialog.getOpenFileName(dialog, "Вибрати файл", "", "Зображення (*.png *.jpg)")

        if file_name:
            label.setText(file_name)

    
    def analyze_ndvi_advanced(self, ndvi_layer_path):
        dataset = gdal.Open(ndvi_layer_path)
        band = dataset.GetRasterBand(1)
        ndvi_array = band.ReadAsArray()

        transform = dataset.GetGeoTransform()
        pixel_size = abs(transform[1] * transform[5])

        categories = {
        'water': ndvi_array < 0,
        'no_vegetation': (ndvi_array >= 0) & (ndvi_array < 0.2),
        'low_vegetation': (ndvi_array >= 0.2) & (ndvi_array < 0.4),
        'medium_vegetation': (ndvi_array >= 0.4) & (ndvi_array < 0.6),
        'high_vegetation': ndvi_array >= 0.6,
    }

        total_pixels = ndvi_array.size
        total_area = total_pixels * pixel_size

        results = {
            'total_area_m2': total_area,
            'ndvi_stats': {
                'min': float(np.min(ndvi_array)),
                'max': float(np.max(ndvi_array)),
                'mean': float(np.mean(ndvi_array)),
                'median': float(np.median(ndvi_array)),
                'std_dev': float(np.std(ndvi_array)),
                'range': float(np.max(ndvi_array) - np.min(ndvi_array))
            },
            'categories': {}
        }

        for category, mask in categories.items():
            area = np.sum(mask) * pixel_size
            percentage = (np.sum(mask) / total_pixels) * 100
            labeled_objects, num_objects = label(mask)
            density = num_objects / total_area if total_area > 0 else 0

            results['categories'][category] = {
                'area_m2': area,
                'percentage': percentage,
                'num_objects': num_objects,
                'object_density_per_km2': density * 1e6
            }

        vegetated_area = (categories['low_vegetation'] |
                        categories['medium_vegetation'] |
                        categories['high_vegetation'])
        non_vegetated_area = (categories['water'] | categories['no_vegetation'])

        results['additional_statistics'] = {
            'vegetated_area_m2': np.sum(vegetated_area) * pixel_size,
            'vegetated_percentage': (np.sum(vegetated_area) / total_pixels) * 100,
            'non_vegetated_area_m2': np.sum(non_vegetated_area) * pixel_size,
            'non_vegetated_percentage': (np.sum(non_vegetated_area) / total_pixels) * 100,
            'dominant_category': max(results['categories'],
                                    key=lambda x: results['categories'][x]['percentage']),
        }

        return results

    
    def generate_ndvi_report_html(self, index_statistics, vector_layer, ndvi_histogram_name, ndvi_color_scale_name, ndvi_jpg_name, ndvi_an):

        if index_statistics['min'] < 0.2:
            minop = "свідчить про дуже низьку рослинність, що є характерним для деградованих або відкритих ґрунтів"
            minrec = "Рекомендується вжити заходів для відновлення рослинності на території, оскільки низький рівень вегетації вказує на деградовані або відкриті ґрунти."
        else:
            minop = "вказує на низьку густоту рослинності, яка може бути присутня на частинах території"
            minrec = "Територія має низьку густоту рослинності, що може вказувати на можливу потребу у покращенні умов для розвитку рослин."

        if index_statistics['max']  >= 0.6:
            maxop = "свідчить про наявність територій з високою густотою рослинності або високою продуктивністю, що є позитивним фактором для розвитку рослин"
            maxrec = "Території з високою густотою рослинності або високою продуктивністю, що є сприятливими для розвитку рослин. Рекомендується зберегти ці території та оптимізувати умови для подальшого розвитку."
        else:
            maxop = "вказує на відсутність зон із оптимальною вегетацією на території, що може свідчити про не дуже сприятливі умови для рослин"
            maxrec = "На території відсутні оптимальні умови для рослинності. Рекомендується провести покращення середовища для досягнення кращих результатів."

        if index_statistics['mean'] > 0.6:
            meanop = "означає, що на більшості території спостерігається високий рівень вегетації, що є ознакою здорових і продуктивних полів"
            meanrec = "Середній рівень вегетації на території вказує на здорові та продуктивні умови для розвитку рослин. Продовжувати підтримувати ці умови для досягнення високих результатів."
        elif index_statistics['mean'] < 0.4:
            meanop = "вказує на переважання проблемних зон, де рослинність може бути значно знижена або зовсім відсутня"
            meanrec = "Потрібно вжити заходів для відновлення рослинності на території, оскільки низький рівень вегетації може свідчити про знижене здоров'я рослин."
        else:
            meanop = "вказує на середній рівень вегетації, що може бути характерним для територій з нормальною, але не оптимальною продуктивністю рослин"
            meanrec = "Територія має середній рівень вегетації, що є ознакою нормальної продуктивності рослин. Можна продовжувати зберігати існуючі умови для підтримки здоров'я рослин."

        if index_statistics['std_dev'] < 0.1:
            std_devop = "свідчить про однорідну вегетацію на території, де зміни в густоті рослинності є мінімальними"
            std_devoprec = "Однорідна вегетація на території дозволяє прогнозувати стабільні умови для розвитку рослин. Необхідно підтримувати ці умови для збереження стабільності."
        else:
            std_devop = "вказує на значну різнорідність у стані рослинності, що може бути ознакою варіацій у вегетаційних умовах на різних частинах території"
            std_devoprec = "Значна різнорідність у стані рослинності вказує на різноманітні умови на території. Рекомендується дослідити ці варіації і вжити заходів для оптимізації умов на різних ділянках."

        conclusion_1 = conclusion_2 = conclusion_3 = " "

        html_head = """
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Звіт з комплексного аналізу території на основі NDVI</title>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }

                .container {
                    background-color: #ffffff;
                    padding: 40px;
                    border-radius: 15px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                    max-width: 1000px;
                    width: 100%;
                }

                h1 {
                    text-align: center;
                    color: #2E8B57;
                    font-size: 2.5rem;
                    margin-bottom: 20px;
                    text-transform: uppercase;
                }

                h2 {
                    color: #2E8B57;
                    font-size: 2rem;
                    margin-bottom: 15px;
                    text-transform: uppercase;
                    border-bottom: 2px solid #ddd;
                    padding-bottom: 10px;
                }

                h3 {
                    color: #3C9D67;
                    font-size: 1.5rem;
                    margin-top: 20px;
                    margin-bottom: 10px;
                }

                p {
                    font-size: 1.15rem;
                    line-height: 1.6;
                    margin-bottom: 20px;
                    color: #333;
                    text-align: justify;
                }

                ul {
                    list-style-type: none;
                    padding-left: 20px;
                }

                li {
                    font-size: 1.15rem;
                    margin-bottom: 12px;
                    color: #555;
                }

                .map {
                    text-align: center;
                    margin: 40px 0;
                }

                .map img {
                    max-width: 100%;
                    height: auto;
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }

                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 40px 0;
                    border-radius: 8px;
                    overflow: hidden;
                }

                table, th, td {
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }

                th {
                    background-color: #f4f4f4;
                    color: #333;
                    font-weight: bold;
                }

                td {
                    background-color: #fafafa;
                }

                .button {
                    background-color: #2E8B57;
                    color: white;
                    padding: 12px 25px;
                    border-radius: 25px;
                    font-size: 1.2rem;
                    text-align: center;
                    display: inline-block;
                    text-decoration: none;
                }

                .button:hover {
                    background-color: #247a4f;
                }

                .card {
                    background-color: #fafafa;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
                    margin-bottom: 30px;
                }

                .card h3 {
                    font-size: 1.4rem;
                    color: #3C9D67;
                }

                .card ul {
                    padding-left: 15px;
                }
            </style>
        </head>
        """
        html_body = f"""
        <body>
            <div class="container">
                <h1>Звіт з комплексного аналізу території на основі індексу NDVI</h1>
                <p><strong>Дата звіту:</strong> <span id="report-date">{datetime.now()}</span></p>
                <p><strong>Об\'єкт аналізу: </strong>Дані дистанційного зондування Землі</p>
                <p><strong>Джерело даних: </strong>USGS Global Visualization Viewer (GloVis, Глобальний переглядач візуалізації)</p>

                <div class="card">
                    <h2>1. Дані та методологія</h2>
                    <ul>
                        <li><strong>Дані: </strong>Супутникові знімки Landsat 8-9 OLI/TIRS C2 L1</li>
                        <p></p>
                        <li><strong>Метод розрахунку NDVI: </strong> NDVI = (NIR - RED) / (NIR + RED)</li>
                        <p></p>
                        <li><strong>Класи NDVI:</strong>
                            <ul>
                                <li>NDVI < 0.2: Відсутність рослинності</li>
                                <li>0.2 ≤ NDVI < 0.4: Низька густота рослинності</li>
                                <li>0.4 ≤ NDVI < 0.6: Середня густота рослинності</li>
                                <li>NDVI ≥ 0.6: Висока густота рослинності</li>
                            </ul>
                        </li>
                    </ul>
                </div>

                <div class="card">
                    <h2>2. Результати</h2>
                    <p></p>
                    <h3>2.1 Загальна характеристика території</h3>
                    <p><strong>Загальна площа території: </strong>{ndvi_an['total_area_m2']} кв.м.</p>
                    <p><strong>Середнє значення індексу NDVI: </strong>{index_statistics['mean']}</p>
                    <p><strong>Мінімальне значення індексу NDVI: </strong>{index_statistics['min']}</p>
                    <p><strong>Максимальне значення індексу NDVI: </strong>{index_statistics['max']}</p>
                    <p><strong>Стандартне відхилення індексу NDVI: </strong>{index_statistics['std_dev']}</p>
                    <p></p>
                    <p></p>
                    <h3>2.2 Характеристика водних об\'єктів</h3>
                    <p><strong>Площа: </strong>{ndvi_an['categories']['water']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток від загальної площі території: </strong>{ndvi_an['categories']['water']['percentage']} кв.м.</p>
                    <p></p>
                    <p></p>
                    <h3>2.3 Характеристика рослинності</h3>
                    <p><strong>Площа території без рослинності: </strong>{ndvi_an['categories']['no_vegetation']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток території без рослинності від загальної площі території: </strong>{ndvi_an['categories']['no_vegetation']['percentage']}</p>
                    <p><strong>Площа території з низькою рослинністю: </strong>{ndvi_an['categories']['low_vegetation']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток території з низькою рослинністю від загальної площі території: </strong>{ndvi_an['categories']['low_vegetation']['percentage']}</p>
                    <p><strong>Площа території з середньою рослинністю: </strong>{ndvi_an['categories']['medium_vegetation']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток території з середньою рослинністю від загальної площі території: </strong>{ndvi_an['categories']['medium_vegetation']['percentage']}</p>
                    <p><strong>Площа території з високою рослинністю: </strong>{ndvi_an['categories']['high_vegetation']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток території з високою рослинністю від загальної площі території: </strong>{ndvi_an['categories']['high_vegetation']['percentage']}</p>
                    <p></p>
                    <p></p>
                    <p>Аналізуючи отримані значення індексу NDVI можна сказати, що мінімальне значення {minop}. Максимальне значення {maxop}. Середнє значення {meanop}. Нормальний розподіл {std_devop}.</p>
                    <p></p>
                    <p></p>
                    <h3>2.4 Картографічні матеріали</h3>
                    <div class="map">
                        <h4>Обрахований індекс NDVI</h4>
                        <img src="{ndvi_jpg_name}" alt="Обрахований індекс NDVI">
                    </div>
                <div class="map">
                        <h4>Гістограма розподілу значень для індексу NDVI</h4>
                        <img src="{ndvi_histogram_name}" alt="Гістограма розподілу значень для індексу NDVI">
                    </div>
                <div class="map">
                        <h4>Карта кольорів для індексу NDVI</h4>
                        <img src="{ndvi_color_scale_name}" alt="Карта кольорів для індексу NDVI">
                    </div>
                </div>

                <div class="card">
                    <h2>3. Рекомендації</h2>
                    <ul>
                        <li>{minrec}</li>
                        <li>{maxrec}</li>
                        <li>{meanrec}</li>
                        <li>{std_devoprec}</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>            
        """
        return html_head + html_body
            

    def run(self):
        raster_layers = [layer for layer in self.iface.mapCanvas(
        ).layers() if isinstance(layer, QgsRasterLayer)]
        vector_layers = [layer for layer in self.iface.mapCanvas(
        ).layers() if isinstance(layer, QgsVectorLayer)]

        if not raster_layers and vector_layers:
            QMessageBox.warning(self.iface.mainWindow(),
                                "Помилка", "Не завантажено растрові та векторні шари!")
            return

        if len(raster_layers) < 1:
            QMessageBox.warning(self.iface.mainWindow(), "Error",
                                "Для отримання статистики потрібен принаймні один растровий шар!")
            return

        else:
            QMessageBox.information(self.iface.mainWindow(
            ), "Info", f"Знайдено {len(raster_layers)} растрових та {len(vector_layers)} векторних шарів")
            ndvi_name, ndvi_histogram_name, ndvi_color_scale_name, ndvi_jpg_name, vector_name = self.ndvi_choice_layers(
                raster_layers, vector_layers)
        
            ndvi_layer = QgsProject.instance().mapLayersByName(ndvi_name)[0]
                        
            vector_layer = QgsProject.instance(
            ).mapLayersByName(vector_name)[0]

            index_statistics = IndexStatistics(self.iface).get_index_statistics(ndvi_layer)
            
            ndvi_layer_path = ndvi_layer.dataProvider().dataSourceUri()
            result = self.analyze_ndvi_advanced(ndvi_layer_path)

            r = self.generate_ndvi_report_html(index_statistics, vector_layer, ndvi_histogram_name, ndvi_color_scale_name, ndvi_jpg_name, result)

            output_path = QFileDialog.getSaveFileName(
                None, "Зберегти звіт", "", "*.html")[0]
            with open(output_path, "w") as file:
                file.write(r)

            QMessageBox.information(
                self.iface.mainWindow(), "Info", "Генерація звіту успішна")


class EVIReportGenerator:

    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface


    def get_action(self) -> QAction:
        action = QAction("EVI Analysis report", self.iface.mainWindow())
        action.setObjectName(" ")
        action.setWhatsThis(" ")
        action.setStatusTip(" ")
        action.triggered.connect(self.run)

        return action


    def evi_choice_layers(self, raster_layers, vector_layers):
        dialog = QDialog()
        dialog.setWindowTitle("Вибір шарів")
        dialog.setFixedSize(300, 300)

        layout = QVBoxLayout()

        evi_combo = QComboBox()
        for layer in raster_layers:
            evi_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("EVI:"))
        layout.addWidget(evi_combo)

        evi_histogram_button = QPushButton("Вибрати файл EVI Histogram")
        selected_histogram_label = QLabel("Файл не вибрано")
        layout.addWidget(QLabel("EVI Histogram:"))
        layout.addWidget(evi_histogram_button)
        layout.addWidget(selected_histogram_label)
        evi_histogram_button.clicked.connect(
            lambda: self.select_file(dialog, selected_histogram_label)
        )
        
        evi_color_scale_button = QPushButton("Вибрати файл EVI color scale")
        selected_color_scale_label = QLabel("Файл не вибрано")
        layout.addWidget(QLabel("EVI color scale:"))
        layout.addWidget(evi_color_scale_button)
        layout.addWidget(selected_color_scale_label)
        evi_color_scale_button.clicked.connect(
            lambda: self.select_file(dialog, selected_color_scale_label)
        )

        evi_jpg_button = QPushButton("Вибрати зображення індексу")
        selected_jpg_label = QLabel("Файл не вибрано")
        layout.addWidget(QLabel("Зображення індексу:"))
        layout.addWidget(evi_jpg_button)
        layout.addWidget(selected_jpg_label)
        evi_jpg_button.clicked.connect(
            lambda: self.select_file(dialog, selected_jpg_label)
        )

        vector_combo = QComboBox()
        for layer in vector_layers:
            vector_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("Vector:"))
        layout.addWidget(vector_combo)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)

        dialog.setLayout(layout)

        if dialog.exec_():
            return evi_combo.currentText(), selected_histogram_label.text(), selected_color_scale_label.text(), selected_jpg_label.text(), vector_combo.currentText()
        return None
    

    def select_file(self, dialog, label):
        file_name, _ = QFileDialog.getOpenFileName(dialog, "Вибрати файл", "", "Зображення (*.png *.jpg)")

        if file_name:
            label.setText(file_name)

    
    def analyze_evi_advanced(self, evi_layer_path):
        dataset = gdal.Open(evi_layer_path)
        band = dataset.GetRasterBand(1)
        evi_array = band.ReadAsArray()

        transform = dataset.GetGeoTransform()
        pixel_size = abs(transform[1] * transform[5])

        categories = {
            'no_vegetation': evi_array < 0.2,
            'low_vegetation': (evi_array >= 0.2) & (evi_array < 0.5),
            'medium_vegetation': (evi_array >= 0.5) & (evi_array < 0.8),
            'high_vegetation': evi_array >= 0.8,
            'intensive_agriculture': evi_array > 0.7,
        }

        total_pixels = evi_array.size
        total_area = total_pixels * pixel_size

        results = {
            'total_area_m2': total_area,
            'evi_stats': {
                'min': float(np.min(evi_array)),
                'max': float(np.max(evi_array)),
                'mean': float(np.mean(evi_array)),
                'median': float(np.median(evi_array)),
                'std_dev': float(np.std(evi_array)),
                'range': float(np.max(evi_array) - np.min(evi_array))
            },
            'categories': {}
        }

        for category, mask in categories.items():
            area = np.sum(mask) * pixel_size
            percentage = (np.sum(mask) / total_pixels) * 100
            labeled_objects, num_objects = label(mask)
            density = num_objects / total_area if total_area > 0 else 0

            results['categories'][category] = {
                'area_m2': area,
                'percentage': percentage,
                'num_objects': num_objects,
                'object_density_per_km2': density * 1e6
            }

        agricultural_area = np.sum(categories['intensive_agriculture']) * pixel_size
        agricultural_percentage = (np.sum(categories['intensive_agriculture']) / total_pixels) * 100

        results['categories']['intensive_agriculture']['area_m2'] = agricultural_area
        results['categories']['intensive_agriculture']['percentage'] = agricultural_percentage

        vegetated_area = (categories['low_vegetation'] |
                        categories['medium_vegetation'] |
                        categories['high_vegetation'])
        non_vegetated_area = categories['no_vegetation']

        results['additional_statistics'] = {
            'vegetated_area_m2': np.sum(vegetated_area) * pixel_size,
            'vegetated_percentage': (np.sum(vegetated_area) / total_pixels) * 100,
            'non_vegetated_area_m2': np.sum(non_vegetated_area) * pixel_size,
            'non_vegetated_percentage': (np.sum(non_vegetated_area) / total_pixels) * 100,
            'dominant_category': max(results['categories'],
                                    key=lambda x: results['categories'][x]['percentage']),
        }

        return results
    

    def generate_evi_report_html(self, index_statistics, vector_layer, evi_histogram_name, evi_color_scale_name, evi_jpg_name, evi_an):

        if index_statistics['min'] < 0.2:
            minop = "свідчить про відсутність рослинності або дуже низьку її щільність, що може бути характерним для деградованих земель, пустельних або сильно засолених територій"
            minrec = "Рекомендується вжити заходи для відновлення рослинності на території, оскільки низька рослинність або її відсутність свідчить про серйозні проблеми з екологічним станом території."
        else:
            minop = "вказує на низьку густоту рослинності, яка може бути результатом недостатньої вологості або поживних речовин, що обмежують розвиток рослин"
            minrec = "Територія має низьку густоту рослинності, що може вказувати на проблеми із здоров'ям рослин або потребу в покращенні умов для їх розвитку, таких як зрошення або внесення добрив."

        if index_statistics['max'] >= 0.8:
            maxop = "свідчить про наявність територій з дуже високою щільністю рослинності, що є характерним для здорових, багатих на біомасу екосистем, таких як тропічні ліси або зрошувані поля"
            maxrec = "Території з високою густотою рослинності потребують збереження і подальшого розвитку, тому що вони мають велику біологічну продуктивність і сприяють поліпшенню екологічного стану території."
        else:
            maxop = "вказує на відсутність значних зон з високою щільністю рослинності, що може бути ознакою поганих умов для рослин або занедбаності території"
            maxrec = "На території відсутні оптимальні умови для розвитку рослинності. Рекомендується покращити середовище для рослин, можливо, через застосування технологій з покращення ґрунтів або збільшення зрошення."

        if index_statistics['mean'] > 0.8:
            meanop = "означає, що більша частина території має дуже високу рослинність, що свідчить про стабільний екологічний стан і хорошу продуктивність рослин"
            meanrec = "Середній рівень рослинності вказує на здорові та продуктивні умови для розвитку рослин. Продовжуйте підтримувати ці умови для досягнення сталого розвитку та високої врожайності."
        elif index_statistics['mean'] < 0.5:
            meanop = "вказує на відсутність значної частини рослинності на території, що може бути спричинено несприятливими умовами або проблемами з екосистемою"
            meanrec = "Потрібно вжити заходів для відновлення рослинності на території, оскільки низький рівень рослинності може свідчити про деградацію екосистеми або відсутність достатніх природних ресурсів."
        else:
            meanop = "вказує на середній рівень рослинності, який може бути характерним для територій з нормальними умовами, але без оптимальної продуктивності рослин"
            meanrec = "Територія має середній рівень рослинності, що свідчить про стабільні, але не максимальні умови для розвитку рослин. Потрібно зберігати наявні умови і, при потребі, вдосконалити їх."

        if index_statistics['std_dev'] < 0.1:
            std_devop = "свідчить про стабільну і однорідну вегетацію на території, де зміни в густоті рослинності є мінімальними, що є ознакою стабільної екосистеми"
            std_devoprec = "Однорідна вегетація на території дозволяє прогнозувати стабільні умови для розвитку рослин. Такі умови сприяють збереженню екологічної рівноваги і сприятливі для сталого сільського господарства."
        else:
            std_devop = "вказує на значну різнорідність у стані рослинності, що може бути ознакою різних екосистем або варіацій у якості ґрунтів і умов вирощування рослин"
            std_devoprec = "Значна різнорідність у стані рослинності вказує на різноманітні умови на території. Рекомендується дослідити ці варіації для оптимізації умов на різних ділянках, а також для адаптації місцевих рослин до мінливих умов."

        html_head = """
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Звіт з комплексного аналізу території на основі EVI</title>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }

                .container {
                    background-color: #ffffff;
                    padding: 40px;
                    border-radius: 15px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                    max-width: 1000px;
                    width: 100%;
                }

                h1 {
                    text-align: center;
                    color: #2E8B57;
                    font-size: 2.5rem;
                    margin-bottom: 20px;
                    text-transform: uppercase;
                }

                h2 {
                    color: #2E8B57;
                    font-size: 2rem;
                    margin-bottom: 15px;
                    text-transform: uppercase;
                    border-bottom: 2px solid #ddd;
                    padding-bottom: 10px;
                }

                h3 {
                    color: #3C9D67;
                    font-size: 1.5rem;
                    margin-top: 20px;
                    margin-bottom: 10px;
                }

                p {
                    font-size: 1.15rem;
                    line-height: 1.6;
                    margin-bottom: 20px;
                    color: #333;
                    text-align: justify;
                }

                ul {
                    list-style-type: none;
                    padding-left: 20px;
                }

                li {
                    font-size: 1.15rem;
                    margin-bottom: 12px;
                    color: #555;
                }

                .map {
                    text-align: center;
                    margin: 40px 0;
                }

                .map img {
                    max-width: 100%;
                    height: auto;
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }

                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 40px 0;
                    border-radius: 8px;
                    overflow: hidden;
                }

                table, th, td {
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }

                th {
                    background-color: #f4f4f4;
                    color: #333;
                    font-weight: bold;
                }

                td {
                    background-color: #fafafa;
                }

                .button {
                    background-color: #2E8B57;
                    color: white;
                    padding: 12px 25px;
                    border-radius: 25px;
                    font-size: 1.2rem;
                    text-align: center;
                    display: inline-block;
                    text-decoration: none;
                }

                .button:hover {
                    background-color: #247a4f;
                }

                .card {
                    background-color: #fafafa;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
                    margin-bottom: 30px;
                }

                .card h3 {
                    font-size: 1.4rem;
                    color: #3C9D67;
                }

                .card ul {
                    padding-left: 15px;
                }
            </style>
        </head>
        """
        html_body = f"""
        <body>
            <div class="container">
                <h1>Звіт з комплексного аналізу території на основі індексу EVI</h1>
                <p><strong>Дата звіту:</strong> <span id="report-date">{datetime.now()}</span></p>
                <p><strong>Об\'єкт аналізу: </strong>Дані дистанційного зондування Землі</p>
                <p><strong>Джерело даних: </strong>USGS Global Visualization Viewer (GloVis, Глобальний переглядач візуалізації)</p>

                <div class="card">
                    <h2>1. Дані та методологія</h2>
                    <ul>
                        <li><strong>Дані: </strong>Супутникові знімки Landsat 8-9 OLI/TIRS C2 L1</li>
                        <p></p>
                        <li><strong>Метод розрахунку EVI: </strong> EVI = G * (NIR - RED) / (NIR + C1 * RED - C2 * BLUE + L)</li>
                        <p></p>
                        <li><strong>Застосовані додаткові коефіцієнти та параметри для кореляції: </strong>
                            <ul>
                                    <li>G (2.5) — коефіцієнт підсилення</li>
                                    <li>C1 (6) — коефіцієнт для корекції синього каналу</li>
                                    <li>C2 (7.5) — коефіцієнт для корекції зеленого каналу</li>
                                    <li>L (10000) — параметр корекції для стабільності індексу</li>
                                </ul>
                        </li>
                        <p></p>
                        <li><strong>Переваги: </strong> Застосований індекс EVI дозволив врахувати додаткові фактори, такі як атмосферні корекції та вплив синього каналу (BLUE), а також дозволив збільшити чутливість до густоти рослинності </li>
                        <p></p>
                        <li><strong>Класи EVI:</strong>
                            <ul>
                                <li>EVI < 0.2: Відсутність рослинності</li>
                                <li>0.2 ≤ EVI < 0.5: Низька густота рослинності</li>
                                <li>0.5 ≤ EVI < 0.8: Середня густота рослинності</li>
                                <li>EVI ≥ 0.8: Висока густота рослинності</li>
                            </ul>
                        </li>
                    </ul>
                </div>

                <div class="card">
                    <h2>2. Результати</h2>
                    <p></p>
                    <h3>2.1 Загальна характеристика території</h3>
                    <p><strong>Загальна площа території: </strong>{evi_an['total_area_m2']} кв.м.</p>
                    <p><strong>Середнє значення індексу EVI: </strong>{index_statistics['mean']}</p>
                    <p><strong>Мінімальне значення індексу EVI: </strong>{index_statistics['min']}</p>
                    <p><strong>Максимальне значення індексу EVI: </strong>{index_statistics['max']}</p>
                    <p><strong>Стандартне відхилення індексу EVI: </strong>{index_statistics['std_dev']}</p>
                    <p></p>
                    <p></p>
                    <h3>2.2 Характеристика рослинності</h3>
                    <p><strong>Площа території без рослинності: </strong>{evi_an['categories']['no_vegetation']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток території без рослинності від загальної площі території: </strong>{evi_an['categories']['no_vegetation']['percentage']}</p>
                    <p><strong>Площа території з низькою рослинністю: </strong>{evi_an['categories']['low_vegetation']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток території з низькою рослинністю від загальної площі території: </strong>{evi_an['categories']['low_vegetation']['percentage']}</p>
                    <p><strong>Площа території з середньою рослинністю: </strong>{evi_an['categories']['medium_vegetation']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток території з середньою рослинністю від загальної площі території: </strong>{evi_an['categories']['medium_vegetation']['percentage']}</p>
                    <p><strong>Площа території з високою рослинністю: </strong>{evi_an['categories']['high_vegetation']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток території з високою рослинністю від загальної площі території: </strong>{evi_an['categories']['high_vegetation']['percentage']}</p>
                    <p><strong>Площа території з високопродуктивною рослинністю: </strong>{evi_an['categories']['high_vegetation']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток території з високопродуктивною рослинністю від загальної площі території: </strong>{evi_an['categories']['high_vegetation']['percentage']}</p>
                    <p><strong>Площа зон інтенсивного сільського господарства: </strong>{evi_an['categories']['intensive_agriculture']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток зон інтенсивного сільського господарства від загальної площі території: </strong>{evi_an['categories']['intensive_agriculture']['percentage']}</p>
                    <p></p>
                    <p></p>
                    <p>Аналізуючи отримані значення індексу EVI можна сказати, що мінімальне значення {minop}. Максимальне значення {maxop}. Середнє значення {meanop}. Нормальний розподіл {std_devop}.</p>
                    <p></p>
                    <p></p>
                    <h3>2.3 Картографічні матеріали</h3>
                    <div class="map">
                        <h4>Обрахований індекс EVI</h4>
                        <img src="{evi_jpg_name}" alt="Обрахований індекс EVI">
                    </div>
                <div class="map">
                        <h4>Гістограма розподілу значень для індексу EVI</h4>
                        <img src="{evi_histogram_name}" alt="Гістограма розподілу значень для індексу EVI">
                    </div>
                <div class="map">
                        <h4>Карта кольорів для індексу EVI</h4>
                        <img src="{evi_color_scale_name}" alt="Карта кольорів для індексу EVI">
                    </div>
                </div>

                <div class="card">
                    <h2>3. Рекомендації</h2>
                    <ul>
                        <li>{minrec}</li>
                        <li>{maxrec}</li>
                        <li>{meanrec}</li>
                        <li>{std_devoprec}</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>            
        """
        return html_head + html_body
            

    def run(self):
        raster_layers = [layer for layer in self.iface.mapCanvas(
        ).layers() if isinstance(layer, QgsRasterLayer)]
        vector_layers = [layer for layer in self.iface.mapCanvas(
        ).layers() if isinstance(layer, QgsVectorLayer)]

        if not raster_layers and vector_layers:
            QMessageBox.warning(self.iface.mainWindow(),
                                "Помилка", "Не завантажено растрові та векторні шари!")
            return

        if len(raster_layers) < 1:
            QMessageBox.warning(self.iface.mainWindow(), "Error",
                                "Для отримання статистики потрібен принаймні один растровий шар!")
            return

        else:
            QMessageBox.information(self.iface.mainWindow(
            ), "Info", f"Знайдено {len(raster_layers)} растрових та {len(vector_layers)} векторних шарів")
            evi_name, evi_histogram_name, evi_color_scale_name, evi_jpg_name, vector_name = self.evi_choice_layers(
                raster_layers, vector_layers)
        
            evi_layer = QgsProject.instance().mapLayersByName(evi_name)[0]
                        
            vector_layer = QgsProject.instance(
            ).mapLayersByName(vector_name)[0]

            index_statistics = IndexStatistics(self.iface).get_index_statistics(evi_layer)
            
            evi_layer_path = evi_layer.dataProvider().dataSourceUri()
            result = self.analyze_evi_advanced(evi_layer_path)

            r = self.generate_evi_report_html(index_statistics, vector_layer, evi_histogram_name, evi_color_scale_name, evi_jpg_name, result)

            output_path = QFileDialog.getSaveFileName(
                None, "Зберегти звіт", "", "*.html")[0]
            with open(output_path, "w") as file:
                file.write(r)

            QMessageBox.information(
                self.iface.mainWindow(), "Info", "Генерація звіту успішна")


class GNDVIReportGenerator:

    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface


    def get_action(self) -> QAction:
        action = QAction("GNDVI Analysis report", self.iface.mainWindow())
        action.setObjectName(" ")
        action.setWhatsThis(" ")
        action.setStatusTip(" ")
        action.triggered.connect(self.run)

        return action


    def gndvi_choice_layers(self, raster_layers, vector_layers):
        dialog = QDialog()
        dialog.setWindowTitle("Вибір шарів")
        dialog.setFixedSize(300, 300)

        layout = QVBoxLayout()

        gndvi_combo = QComboBox()
        for layer in raster_layers:
            gndvi_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("GNDVI:"))
        layout.addWidget(gndvi_combo)

        gndvi_histogram_button = QPushButton("Вибрати файл GNDVI Histogram")
        selected_histogram_label = QLabel("Файл не вибрано")
        layout.addWidget(QLabel("GNDVI Histogram:"))
        layout.addWidget(gndvi_histogram_button)
        layout.addWidget(selected_histogram_label)
        gndvi_histogram_button.clicked.connect(
            lambda: self.select_file(dialog, selected_histogram_label)
        )
        
        gndvi_color_scale_button = QPushButton("Вибрати файл GNDVI color scale")
        selected_color_scale_label = QLabel("Файл не вибрано")
        layout.addWidget(QLabel("GNDVI color scale:"))
        layout.addWidget(gndvi_color_scale_button)
        layout.addWidget(selected_color_scale_label)
        gndvi_color_scale_button.clicked.connect(
            lambda: self.select_file(dialog, selected_color_scale_label)
        )

        gndvi_jpg_button = QPushButton("Вибрати зображення індексу")
        selected_jpg_label = QLabel("Файл не вибрано")
        layout.addWidget(QLabel("Зображення індексу:"))
        layout.addWidget(gndvi_jpg_button)
        layout.addWidget(selected_jpg_label)
        gndvi_jpg_button.clicked.connect(
            lambda: self.select_file(dialog, selected_jpg_label)
        )

        vector_combo = QComboBox()
        for layer in vector_layers:
            vector_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("Vector:"))
        layout.addWidget(vector_combo)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)

        dialog.setLayout(layout)

        if dialog.exec_():
            return gndvi_combo.currentText(), selected_histogram_label.text(), selected_color_scale_label.text(), selected_jpg_label.text(), vector_combo.currentText()
        return None
    

    def select_file(self, dialog, label):
        file_name, _ = QFileDialog.getOpenFileName(dialog, "Вибрати файл", "", "Зображення (*.png *.jpg)")

        if file_name:
            label.setText(file_name)

    
    def analyze_gndvi_advanced(self, gndvi_layer_path):
        dataset = gdal.Open(gndvi_layer_path)
        band = dataset.GetRasterBand(1)
        gndvi_array = band.ReadAsArray()

        transform = dataset.GetGeoTransform()
        pixel_size = abs(transform[1] * transform[5])

        categories = {
            'stress_zones': (gndvi_array >= 0.2) & (gndvi_array < 0.4),
            'photosynthetically_active': gndvi_array >= 0.5
        }

        total_pixels = gndvi_array.size
        total_area = total_pixels * pixel_size

        results = {
            'total_area_m2': total_area,
            'gndvi_stats': {
                'std_dev': float(np.std(gndvi_array)),
                'range': float(np.max(gndvi_array) - np.min(gndvi_array))
            },
            'categories': {}
        }

        for category, mask in categories.items():
            area = np.sum(mask) * pixel_size
            percentage = (np.sum(mask) / total_pixels) * 100
            labeled_objects, num_objects = label(mask)
            density = num_objects / total_area if total_area > 0 else 0

            results['categories'][category] = {
                'area_m2': area,
                'percentage': percentage,
                'num_objects': num_objects,
                'object_density_per_km2': density * 1e6
            }

        stress_area = categories['stress_zones']
        active_photosynthesis_area = categories['photosynthetically_active']

        results['additional_statistics'] = {
            'stress_area_m2': np.sum(stress_area) * pixel_size,
            'stress_area_percentage': (np.sum(stress_area) / total_pixels) * 100,
            'active_photosynthesis_area_m2': np.sum(active_photosynthesis_area) * pixel_size,
            'active_photosynthesis_percentage': (np.sum(active_photosynthesis_area) / total_pixels) * 100,
        }

        return results
    

    def generate_gndvi_report_html(self, index_statistics, vector_layer, gndvi_histogram_name, gndvi_color_scale_name, gndvi_jpg_name, gndvi_an):

        if index_statistics['min'] < 0.2:
            minop = "свідчить про мінімальну або відсутню рослинність, що є ознакою деградованих ґрунтів або зон з дуже поганими умовами для рослинності"
            minrec = "Необхідно вжити заходів для відновлення рослинності, таких як зрошення або внесення добрив, для покращення екологічного стану території."

        elif index_statistics['min'] < 0.4:
            minop = "вказує на низьку густоту рослинності, що може бути викликано недостатньою вологою або іншими стресовими факторами"
            minrec = "Рекомендується вжити заходи для покращення умов росту рослин, наприклад, через зрошення або поліпшення родючості ґрунтів."

        elif index_statistics['min'] < 0.6:
            minop = "свідчить про середню густоту рослинності, що може бути ознакою помірних умов для рослин"
            minrec = "Територія має помірну густоту рослинності. Потрібно продовжувати підтримувати ці умови для стабільного розвитку рослин."

        else:
            minop = "вказує на високу густоту рослинності, що є характерним для здорових екосистем або зрошуваних сільськогосподарських територій"
            minrec = "Рекомендується зберігати ці умови та продовжувати підтримувати високий рівень фотосинтетичної активності."

        if index_statistics['max'] >= 0.6:
            maxop = "свідчить про високий рівень фотосинтетичної активності та здорову рослинність на території"
            maxrec = "Зони з високим рівнем GNDVI потребують підтримки для збереження їх біологічної продуктивності."

        elif index_statistics['max'] >= 0.4:
            maxop = "вказує на середній рівень рослинності, що може бути ознакою нормальних умов для більшості рослин"
            maxrec = "Зона з середньою рослинністю потребує покращення умов для досягнення більш високих результатів."

        else:
            maxop = "свідчить про відсутність значної фотосинтетичної активності, що потребує втручання для покращення умов для рослин"
            maxrec = "Рекомендується вжити заходи для поліпшення умов для розвитку рослин на території."

        if index_statistics['mean'] >= 0.6:
            meanop = "означає, що більша частина території має високу фотосинтетичну активність, що є ознакою здорових рослин і хороших умов для їх розвитку"
            meanrec = "Продовжуйте підтримувати ці умови для досягнення стабільного розвитку рослин."

        elif index_statistics['mean'] < 0.4:
            meanop = "вказує на низький рівень рослинності, що може бути спричинено несприятливими умовами для росту рослин"
            meanrec = "Необхідно вжити заходів для покращення умов на території, таких як зрошення або поліпшення родючості ґрунтів."

        else:
            meanop = "вказує на середній рівень рослинності, що може бути ознакою стабільних умов для рослин"
            meanrec = "Рекомендується продовжувати підтримувати ці умови для досягнення максимального розвитку рослин."

        if index_statistics['std_dev'] < 0.1:
            std_devop = "вказує на стабільні умови для рослин, де зміни у густоті рослинності мінімальні"
            std_devoprec = "Збереження стабільності в екосистемі дозволяє досягти сталого розвитку сільського господарства."

        else:
            std_devop = "свідчить про значну варіативність у рівнях рослинності, що може бути ознакою різнорідних екосистем або різних умов для росту рослин"
            std_devoprec = "Необхідно дослідити різноманітні умови на території для оптимізації зрошення та поліпшення родючості ґрунтів."

        html_head = """
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Звіт з комплексного аналізу території на основі GNDVI</title>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }

                .container {
                    background-color: #ffffff;
                    padding: 40px;
                    border-radius: 15px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                    max-width: 1000px;
                    width: 100%;
                }

                h1 {
                    text-align: center;
                    color: #2E8B57;
                    font-size: 2.5rem;
                    margin-bottom: 20px;
                    text-transform: uppercase;
                }

                h2 {
                    color: #2E8B57;
                    font-size: 2rem;
                    margin-bottom: 15px;
                    text-transform: uppercase;
                    border-bottom: 2px solid #ddd;
                    padding-bottom: 10px;
                }

                h3 {
                    color: #3C9D67;
                    font-size: 1.5rem;
                    margin-top: 20px;
                    margin-bottom: 10px;
                }

                p {
                    font-size: 1.15rem;
                    line-height: 1.6;
                    margin-bottom: 20px;
                    color: #333;
                    text-align: justify;
                }

                ul {
                    list-style-type: none;
                    padding-left: 20px;
                }

                li {
                    font-size: 1.15rem;
                    margin-bottom: 12px;
                    color: #555;
                }

                .map {
                    text-align: center;
                    margin: 40px 0;
                }

                .map img {
                    max-width: 100%;
                    height: auto;
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }

                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 40px 0;
                    border-radius: 8px;
                    overflow: hidden;
                }

                table, th, td {
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }

                th {
                    background-color: #f4f4f4;
                    color: #333;
                    font-weight: bold;
                }

                td {
                    background-color: #fafafa;
                }

                .button {
                    background-color: #2E8B57;
                    color: white;
                    padding: 12px 25px;
                    border-radius: 25px;
                    font-size: 1.2rem;
                    text-align: center;
                    display: inline-block;
                    text-decoration: none;
                }

                .button:hover {
                    background-color: #247a4f;
                }

                .card {
                    background-color: #fafafa;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
                    margin-bottom: 30px;
                }

                .card h3 {
                    font-size: 1.4rem;
                    color: #3C9D67;
                }

                .card ul {
                    padding-left: 15px;
                }
            </style>
        </head>
        """
        html_body = f"""
        <body>
            <div class="container">
                <h1>Звіт з комплексного аналізу території на основі індексу GNDVI</h1>
                <p><strong>Дата звіту:</strong> <span id="report-date">{datetime.now()}</span></p>
                <p><strong>Об\'єкт аналізу: </strong>Дані дистанційного зондування Землі</p>
                <p><strong>Джерело даних: </strong>USGS Global Visualization Viewer (GloVis, Глобальний переглядач візуалізації)</p>

                <div class="card">
                    <h2>1. Дані та методологія</h2>
                    <ul>
                        <li><strong>Дані: </strong>Супутникові знімки Landsat 8-9 OLI/TIRS C2 L1</li>
                        <p></p>
                        <li><strong>Метод розрахунку GNDVI: </strong> GNDVI = (NIR - Green) / (NIR + Green)</li>
                        <p></p>
                        <li><strong>Переваги: </strong> Індекс GNDVI дозволяє точно оцінювати стан рослинності, виявляти стрес, визначати рівень фотосинтетичної активності та ефективно моніторити сільськогосподарські землі </li>
                        <p></p>
                        <li><strong>Класи GNDVI:</strong>
                            <ul>
                                <li>GNDVI < 0.2: Мінімальна або відсутня рослинність</li>
                                <li>0.2 ≤ GNDVI < 0.4: Низька густота рослинності</li>
                                <li>0.4 ≤ GNDVI < 0.6: Середня густота рослинності</li>
                                <li>GNDVI ≥ 0.6: Висока густота рослинності</li>
                            </ul>
                        </li>
                    </ul>
                </div>

                <div class="card">
                    <h2>2. Результати</h2>
                    <p></p>
                    <h3>2.1 Загальна характеристика території</h3>
                    <p><strong>Загальна площа території: </strong>{gndvi_an['total_area_m2']} кв.м.</p>
                    <p><strong>Середнє значення індексу GNDVI: </strong>{index_statistics['mean']}</p>
                    <p><strong>Мінімальне значення індексу GNDVI: </strong>{index_statistics['min']}</p>
                    <p><strong>Максимальне значення індексу GNDVI: </strong>{index_statistics['max']}</p>
                    <p><strong>Стандартне відхилення індексу GNDVI: </strong>{index_statistics['std_dev']}</p>
                    <p></p>
                    <p></p>
                    <h3>2.2 Аналіз рослинності за GNDVI</h3>
                    <li><strong>Площа зони стресу рослин: </strong>{gndvi_an['categories']['stress_zones']['area_m2']} кв.м.</li>
                    <li><strong>Відсоток зони стресу рослин від загальної площі території: </strong>{gndvi_an['categories']['stress_zones']['percentage']}</li>
                    <li><strong>Площа фотосинтетично активних зон: </strong>{gndvi_an['categories']['photosynthetically_active']['area_m2']} кв.м.</li>
                    <li><strong>Відсоток фотосинтетично активних зон від загальної площі території: </strong>{gndvi_an['categories']['photosynthetically_active']['percentage']}</li>
                    <p></p>
                    <p></p>
                    <p>Аналізуючи отримані значення індексу GNDVI можна сказати, що мінімальне значення {minop}. Максимальне значення {maxop}. Середнє значення {meanop}. Нормальний розподіл {std_devop}.</p>
                    <p></p>
                    <p></p>
                    <h3>2.3 Картографічні матеріали</h3>
                    <div class="map">
                        <h4>Обрахований індекс GNDVI</h4>
                        <img src="{gndvi_jpg_name}" alt="Обрахований індекс GNDVI">
                    </div>
                <div class="map">
                        <h4>Гістограма розподілу значень для індексу GNDVI</h4>
                        <img src="{gndvi_histogram_name}" alt="Гістограма розподілу значень для індексу GNDVI">
                    </div>
                <div class="map">
                        <h4>Карта кольорів для індексу GNDVI</h4>
                        <img src="{gndvi_color_scale_name}" alt="Карта кольорів для індексу GNDVI">
                    </div>
                </div>

                <div class="card">
                    <h2>3. Рекомендації</h2>
                    <ul>
                        <li>{minrec}</li>
                        <li>{maxrec}</li>
                        <li>{meanrec}</li>
                        <li>{std_devoprec}</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>            
        """
        return html_head + html_body
            

    def run(self):
        raster_layers = [layer for layer in self.iface.mapCanvas(
        ).layers() if isinstance(layer, QgsRasterLayer)]
        vector_layers = [layer for layer in self.iface.mapCanvas(
        ).layers() if isinstance(layer, QgsVectorLayer)]

        if not raster_layers and vector_layers:
            QMessageBox.warning(self.iface.mainWindow(),
                                "Помилка", "Не завантажено растрові та векторні шари!")
            return

        if len(raster_layers) < 1:
            QMessageBox.warning(self.iface.mainWindow(), "Error",
                                "Для отримання статистики потрібен принаймні один растровий шар!")
            return

        else:
            QMessageBox.information(self.iface.mainWindow(
            ), "Info", f"Знайдено {len(raster_layers)} растрових та {len(vector_layers)} векторних шарів")
            gndvi_name, gndvi_histogram_name, gndvi_color_scale_name, gndvi_jpg_name, vector_name = self.gndvi_choice_layers(
                raster_layers, vector_layers)
        
            gndvi_layer = QgsProject.instance().mapLayersByName(gndvi_name)[0]
                        
            vector_layer = QgsProject.instance(
            ).mapLayersByName(vector_name)[0]

            index_statistics = IndexStatistics(self.iface).get_index_statistics(gndvi_layer)
            
            gndvi_layer_path = gndvi_layer.dataProvider().dataSourceUri()
            result = self.analyze_gndvi_advanced(gndvi_layer_path)

            r = self.generate_gndvi_report_html(index_statistics, vector_layer, gndvi_histogram_name, gndvi_color_scale_name, gndvi_jpg_name, result)

            output_path = QFileDialog.getSaveFileName(
                None, "Зберегти звіт", "", "*.html")[0]
            with open(output_path, "w") as file:
                file.write(r)

            QMessageBox.information(
                self.iface.mainWindow(), "Info", "Генерація звіту успішна")


class CVIReportGenerator:

    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface


    def get_action(self) -> QAction:
        action = QAction("CVI Analysis report", self.iface.mainWindow())
        action.setObjectName(" ")
        action.setWhatsThis(" ")
        action.setStatusTip(" ")
        action.triggered.connect(self.run)

        return action


    def cvi_choice_layers(self, raster_layers, vector_layers):
        dialog = QDialog()
        dialog.setWindowTitle("Вибір шарів")
        dialog.setFixedSize(300, 300)

        layout = QVBoxLayout()

        cvi_combo = QComboBox()
        for layer in raster_layers:
            cvi_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("CVI:"))
        layout.addWidget(cvi_combo)

        cvi_histogram_button = QPushButton("Вибрати файл CVI Histogram")
        selected_histogram_label = QLabel("Файл не вибрано")
        layout.addWidget(QLabel("CVI Histogram:"))
        layout.addWidget(cvi_histogram_button)
        layout.addWidget(selected_histogram_label)
        cvi_histogram_button.clicked.connect(
            lambda: self.select_file(dialog, selected_histogram_label)
        )
        
        cvi_color_scale_button = QPushButton("Вибрати файл CVI color scale")
        selected_color_scale_label = QLabel("Файл не вибрано")
        layout.addWidget(QLabel("CVI color scale:"))
        layout.addWidget(cvi_color_scale_button)
        layout.addWidget(selected_color_scale_label)
        cvi_color_scale_button.clicked.connect(
            lambda: self.select_file(dialog, selected_color_scale_label)
        )

        cvi_jpg_button = QPushButton("Вибрати зображення індексу")
        selected_jpg_label = QLabel("Файл не вибрано")
        layout.addWidget(QLabel("Зображення індексу:"))
        layout.addWidget(cvi_jpg_button)
        layout.addWidget(selected_jpg_label)
        cvi_jpg_button.clicked.connect(
            lambda: self.select_file(dialog, selected_jpg_label)
        )

        vector_combo = QComboBox()
        for layer in vector_layers:
            vector_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("Vector:"))
        layout.addWidget(vector_combo)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)

        dialog.setLayout(layout)

        if dialog.exec_():
            return cvi_combo.currentText(), selected_histogram_label.text(), selected_color_scale_label.text(), selected_jpg_label.text(), vector_combo.currentText()
        return None
    

    def select_file(self, dialog, label):
        file_name, _ = QFileDialog.getOpenFileName(dialog, "Вибрати файл", "", "Зображення (*.png *.jpg)")

        if file_name:
            label.setText(file_name)

    
    def analyze_cvi_advanced(self, cvi_layer_path):
        dataset = gdal.Open(cvi_layer_path)
        band = dataset.GetRasterBand(1)
        cvi_array = band.ReadAsArray()

        transform = dataset.GetGeoTransform()
        pixel_size = abs(transform[1] * transform[5])

        categories = {
            'minimal_or_absent_vegetation': cvi_array < 0.1,
            'low_vegetation_density': (cvi_array >= 0.1) & (cvi_array < 0.2),
            'medium_vegetation_density': (cvi_array >= 0.2) & (cvi_array < 0.4),
            'high_vegetation_density': cvi_array >= 0.4
        }

        total_pixels = cvi_array.size
        total_area = total_pixels * pixel_size

        results = {
            'total_area_m2': total_area,
            'cvi_stats': {
                'std_dev': float(np.std(cvi_array)),
                'mean': float(np.mean(cvi_array)),
                'min': float(np.min(cvi_array)),
                'max': float(np.max(cvi_array)),
            },
            'categories': {},
            'additional_statistics': {}
        }

        for category, mask in categories.items():
            area = np.sum(mask) * pixel_size
            percentage = (np.sum(mask) / total_pixels) * 100
            min_value = np.min(cvi_array[mask]) if np.any(mask) else None
            max_value = np.max(cvi_array[mask]) if np.any(mask) else None

            pixel_density = np.sum(mask) / total_pixels

            results['categories'][category] = {
                'area_m2': area,
                'percentage': percentage,
                'min_value': min_value,
                'max_value': max_value,
                'pixel_density': pixel_density
            }

        stress_zones = categories['minimal_or_absent_vegetation']
        restoration_potential_zones = categories['low_vegetation_density']

        results['additional_statistics'] = {
            'stress_zones_m2': np.sum(stress_zones) * pixel_size,
            'stress_zones_percentage': (np.sum(stress_zones) / total_pixels) * 100,
            'restoration_potential_zones_m2': np.sum(restoration_potential_zones) * pixel_size,
            'restoration_potential_zones_percentage': (np.sum(restoration_potential_zones) / total_pixels) * 100,
            'ecological_stability': float(np.mean(cvi_array))  # Середнє значення як стабільність
        }

        return results

    def generate_cvi_report_html(self, index_statistics, vector_layer, cvi_histogram_name, cvi_color_scale_name, cvi_jpg_name, cvi_an):

        if index_statistics['min'] < 0.1:
            minop = "свідчить про мінімальну або відсутню рослинність, що є ознакою деградованих ґрунтів або зон з дуже поганими умовами для рослинності"
            minrec = "Необхідно вжити термінові заходи для відновлення рослинності, такі як зрошення, внесення добрив або поліпшення структури ґрунту."

        elif index_statistics['min'] < 0.2:
            minop = "вказує на низьку густоту рослинності, що може бути спричинено несприятливими умовами або дефіцитом води"
            minrec = "Рекомендується застосувати покращення умов для рослин, такі як зрошення, внесення добрив, або поліпшення агротехнічних заходів."

        elif index_statistics['min'] < 0.4:
            minop = "свідчить про середню густоту рослинності, що є характерним для більшості сільськогосподарських територій з нормальною родючістю ґрунтів"
            minrec = "Зона має стабільні умови для розвитку рослин. Продовжуйте підтримувати ці умови для забезпечення стабільного розвитку рослин."

        else:
            minop = "вказує на високу густоту рослинності, що свідчить про здорову екосистему або зрошувані сільськогосподарські території"
            minrec = "Необхідно підтримувати ці умови для забезпечення сталого розвитку екосистеми і збереження високої біологічної продуктивності."

        if index_statistics['max'] >= 0.4:
            maxop = "свідчить про високу фотосинтетичну активність і значну рослинність на території"
            maxrec = "Зони з високим рівнем CVI потребують підтримки для збереження біологічної продуктивності та екосистемної стабільності."

        elif index_statistics['max'] >= 0.2:
            maxop = "вказує на середній рівень рослинності, що є ознакою нормальних умов для більшості рослин"
            maxrec = "Зона з середнім рівнем CVI потребує покращення умов для досягнення більш високої біологічної продуктивності."

        else:
            maxop = "свідчить про відсутність значної фотосинтетичної активності, що потребує значного втручання для покращення умов для рослин"
            maxrec = "Рекомендується терміново вжити заходів для поліпшення умов розвитку рослин на території."

        if index_statistics['mean'] >= 0.4:
            meanop = "означає, що більша частина території має високу фотосинтетичну активність і здорову рослинність"
            meanrec = "Продовжуйте підтримувати ці умови для забезпечення стабільного розвитку рослин та збереження високої продуктивності екосистеми."

        elif index_statistics['mean'] < 0.2:
            meanop = "вказує на низький рівень рослинності, що є ознакою поганих умов для росту рослин"
            meanrec = "Необхідно вжити заходи для покращення умов, таких як зрошення, поліпшення родючості ґрунтів або захист від ерозії."

        else:
            meanop = "вказує на середній рівень рослинності, що може бути ознакою стабільних умов для рослин"
            meanrec = "Рекомендується продовжувати підтримувати ці умови для досягнення максимального розвитку рослин."

        if index_statistics['std_dev'] < 0.1:
            std_devop = "вказує на стабільні умови для рослин, де зміни в густоті рослинності мінімальні"
            std_devoprec = "Збереження стабільних умов екосистеми дозволяє досягти сталого розвитку та зберегти біорізноманіття."

        else:
            std_devop = "свідчить про значну варіативність у рівнях рослинності, що може бути ознакою різнорідних екосистем або нестабільних умов для росту рослин"
            std_devoprec = "Необхідно дослідити варіативність умов на території для оптимізації зрошення, поліпшення родючості ґрунтів та покращення екосистемних послуг."

        html_head = """
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Звіт з комплексного аналізу території на основі CVI</title>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }

                .container {
                    background-color: #ffffff;
                    padding: 40px;
                    border-radius: 15px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                    max-width: 1000px;
                    width: 100%;
                }

                h1 {
                    text-align: center;
                    color: #2E8B57;
                    font-size: 2.5rem;
                    margin-bottom: 20px;
                    text-transform: uppercase;
                }

                h2 {
                    color: #2E8B57;
                    font-size: 2rem;
                    margin-bottom: 15px;
                    text-transform: uppercase;
                    border-bottom: 2px solid #ddd;
                    padding-bottom: 10px;
                }

                h3 {
                    color: #3C9D67;
                    font-size: 1.5rem;
                    margin-top: 20px;
                    margin-bottom: 10px;
                }

                p {
                    font-size: 1.15rem;
                    line-height: 1.6;
                    margin-bottom: 20px;
                    color: #333;
                    text-align: justify;
                }

                ul {
                    list-style-type: none;
                    padding-left: 20px;
                }

                li {
                    font-size: 1.15rem;
                    margin-bottom: 12px;
                    color: #555;
                }

                .map {
                    text-align: center;
                    margin: 40px 0;
                }

                .map img {
                    max-width: 100%;
                    height: auto;
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }

                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 40px 0;
                    border-radius: 8px;
                    overflow: hidden;
                }

                table, th, td {
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }

                th {
                    background-color: #f4f4f4;
                    color: #333;
                    font-weight: bold;
                }

                td {
                    background-color: #fafafa;
                }

                .button {
                    background-color: #2E8B57;
                    color: white;
                    padding: 12px 25px;
                    border-radius: 25px;
                    font-size: 1.2rem;
                    text-align: center;
                    display: inline-block;
                    text-decoration: none;
                }

                .button:hover {
                    background-color: #247a4f;
                }

                .card {
                    background-color: #fafafa;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
                    margin-bottom: 30px;
                }

                .card h3 {
                    font-size: 1.4rem;
                    color: #3C9D67;
                }

                .card ul {
                    padding-left: 15px;
                }
            </style>
        </head>
        """
        html_body = f"""
        <body>
            <div class="container">
                <h1>Звіт з комплексного аналізу території на основі індексу CVI</h1>
                <p><strong>Дата звіту:</strong> <span id="report-date">{datetime.now()}</span></p>
                <p><strong>Об\'єкт аналізу: </strong>Дані дистанційного зондування Землі</p>
                <p><strong>Джерело даних: </strong>USGS Global Visualization Viewer (GloVis, Глобальний переглядач візуалізації)</p>

                <div class="card">
                    <h2>1. Дані та методологія</h2>
                    <ul>
                        <li><strong>Дані: </strong>Супутникові знімки Landsat 8-9 OLI/TIRS C2 L1</li>
                        <p></p>
                        <li><strong>Метод розрахунку CVI: </strong> CVI = (NIR - RED) / (NIR + RED)</li>
                        <p></p>
                        <li><strong>Переваги: </strong> CVI дозволяє ефективно оцінювати здоров'я рослин та рівень хлорофілу, що допомагає моніторити стрес, врожайність і екологічні умови на великих територіях </li>
                        <p></p>
                        <li><strong>Класи CVI:</strong>
                            <ul>
                                <li>CVI < 0.1: Мінімальна або відсутня рослинність</li>
                                <li>0.1 ≤ CVI < 0.2: Низька густота рослинності</li>
                                <li>0.4 ≤ CVI < 0.4: Середня густота рослинності</li>
                                <li>CVI ≥ 0.4: Висока густота рослинності</li>
                            </ul>
                        </li>
                    </ul>
                </div>

                <div class="card">
                    <h2>2. Результати</h2>
                    <p></p>
                    <h3>2.1 Загальна характеристика території</h3>
                    <p><strong>Загальна площа території: </strong>{cvi_an['total_area_m2']} кв.м.</p>
                    <p><strong>Середнє значення індексу CVI: </strong>{index_statistics['mean']}</p>
                    <p><strong>Мінімальне значення індексу CVI: </strong>{index_statistics['min']}</p>
                    <p><strong>Максимальне значення індексу CVI: </strong>{index_statistics['max']}</p>
                    <p><strong>Стандартне відхилення індексу CVI: </strong>{index_statistics['std_dev']}</p>
                    <p></p>
                    <p></p>
                    <h3>2.2 Аналіз стану рослинності за CVI</h3>
                    <p><strong>Площа зони стресу: </strong>{cvi_an['categories']['minimal_or_absent_vegetation']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток зони стресу від загальної площі території: </strong>{cvi_an['categories']['minimal_or_absent_vegetation']['percentage']}</p>
                    <p><strong>Площа зони з високим потенціалом для відновлення: </strong>{cvi_an['categories']['low_vegetation_density']['area_m2']} кв.м.</p>
                    <p><strong>Відсоток зони з високим потенціалом для відновлення від загальної площі території: </strong>{cvi_an['categories']['low_vegetation_density']['percentage']}</p>
                    <p></p>
                    <p></p>
                    <p>Аналізуючи отримані значення індексу GNDVI можна сказати, що мінімальне значення {minop}. Максимальне значення {maxop}. Середнє значення {meanop}. Нормальний розподіл {std_devop}.</p>
                    <p></p>
                    <p></p>
                    <h3>2.3 Картографічні матеріали</h3>
                    <div class="map">
                        <h4>Обрахований індекс GNDVI</h4>
                        <img src="{cvi_jpg_name}" alt="Обрахований індекс GNDVI">
                    </div>
                <div class="map">
                        <h4>Гістограма розподілу значень для індексу GNDVI</h4>
                        <img src="{cvi_histogram_name}" alt="Гістограма розподілу значень для індексу GNDVI">
                    </div>
                <div class="map">
                        <h4>Карта кольорів для індексу GNDVI</h4>
                        <img src="{cvi_color_scale_name}" alt="Карта кольорів для індексу GNDVI">
                    </div>
                </div>

                <div class="card">
                    <h2>3. Рекомендації</h2>
                    <ul>
                        <li>{minrec}</li>
                        <li>{maxrec}</li>
                        <li>{meanrec}</li>
                        <li>{std_devoprec}</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>            
        """
        return html_head + html_body
            

    def run(self):
        raster_layers = [layer for layer in self.iface.mapCanvas(
        ).layers() if isinstance(layer, QgsRasterLayer)]
        vector_layers = [layer for layer in self.iface.mapCanvas(
        ).layers() if isinstance(layer, QgsVectorLayer)]

        if not raster_layers and vector_layers:
            QMessageBox.warning(self.iface.mainWindow(),
                                "Помилка", "Не завантажено растрові та векторні шари!")
            return

        if len(raster_layers) < 1:
            QMessageBox.warning(self.iface.mainWindow(), "Error",
                                "Для отримання статистики потрібен принаймні один растровий шар!")
            return

        else:
            QMessageBox.information(self.iface.mainWindow(
            ), "Info", f"Знайдено {len(raster_layers)} растрових та {len(vector_layers)} векторних шарів")
            cvi_name, cvi_histogram_name, cvi_color_scale_name, cvi_jpg_name, vector_name = self.cvi_choice_layers(
                raster_layers, vector_layers)
        
            cvi_layer = QgsProject.instance().mapLayersByName(cvi_name)[0]
                        
            vector_layer = QgsProject.instance(
            ).mapLayersByName(vector_name)[0]

            index_statistics = IndexStatistics(self.iface).get_index_statistics(cvi_layer)
            
            cvi_layer_path = cvi_layer.dataProvider().dataSourceUri()
            result = self.analyze_cvi_advanced(cvi_layer_path)

            r = self.generate_cvi_report_html(index_statistics, vector_layer, cvi_histogram_name, cvi_color_scale_name, cvi_jpg_name, result)

            output_path = QFileDialog.getSaveFileName(
                None, "Зберегти звіт", "", "*.html")[0]
            with open(output_path, "w") as file:
                file.write(r)

            QMessageBox.information(
                self.iface.mainWindow(), "Info", "Генерація звіту успішна")