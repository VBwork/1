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
    QgsGeometry,
    QgsRectangle,
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

from qgis.utils import iface


class IndexStatistics:

    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface

    def get_action(self) -> QAction:
        action = QAction("Analysis", self.iface.mainWindow())
        action.setObjectName(" ")
        action.setWhatsThis(" ")
        action.setStatusTip(" ")
        action.triggered.connect(self.run)

        return action

    def choice_layers(self, raster_layers, vector_layers):
        dialog = QDialog()
        dialog.setWindowTitle("Вибір індексу")
        dialog.setFixedSize(300, 300)

        layout = QVBoxLayout()

        ndvi_combo = QComboBox()
        for layer in raster_layers:
            ndvi_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("NDVI:"))
        layout.addWidget(ndvi_combo)

        evi_combo = QComboBox()
        for layer in raster_layers:
            evi_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("EVI:"))
        layout.addWidget(evi_combo)

        gndvi_combo = QComboBox()
        for layer in raster_layers:
            gndvi_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("GNDVI:"))
        layout.addWidget(gndvi_combo)

        cvi_combo = QComboBox()
        for layer in raster_layers:
            cvi_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("CVI:"))
        layout.addWidget(cvi_combo)

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
            return ndvi_combo.currentText(), evi_combo.currentText(), gndvi_combo.currentText(), cvi_combo.currentText(), vector_combo.currentText()
        return None

    def get_index_statistics(self, index_layer):

        stats = index_layer.dataProvider().bandStatistics(1)
        return {
            "min": stats.minimumValue,
            "max": stats.maximumValue,
            "mean": stats.mean,
            "std_dev": stats.stdDev,
        }


    def add_attributes(self, vector_layer, raster_layer, prefix):

        provider = vector_layer.dataProvider()
        fields = vector_layer.fields()

        attributes = [f"{prefix}_mean", f"{prefix}_min", f"{prefix}_max", f"{prefix}_std_dev"]
        new_fields = [QgsField(name=attr, type=QVariant.Double) for attr in attributes if fields.lookupField(attr) == -1]

        if new_fields:
            provider.addAttributes(new_fields)
            vector_layer.updateFields()

        stats = self.get_index_statistics(raster_layer)

        if not vector_layer.isEditable():
            vector_layer.startEditing()

        for feature in vector_layer.getFeatures():
            feature_id = feature.id()
            provider.changeAttributeValues({
                feature_id: {
                    fields.indexOf(f"{prefix}_mean"): stats["mean"],
                    fields.indexOf(f"{prefix}_min"): stats["min"],
                    fields.indexOf(f"{prefix}_max"): stats["max"],
                    fields.indexOf(f"{prefix}_std_dev"): stats["std_dev"]
                }
            })

        vector_layer.commitChanges()


    def create_histogram(self, index_layer: QgsRasterLayer, output_path):
        
        stats = self.get_index_statistics(index_layer)

        provider = index_layer.dataProvider()
        extent = index_layer.extent()
        width = index_layer.width()
        height = index_layer.height()

        values = []

        step = 10
        for x in range(0, width, step):
            for y in range(0, height, step):
                
                result = provider.identify(QgsPointXY(extent.xMinimum() + x * index_layer.rasterUnitsPerPixelX(), 
                                                    extent.yMaximum() - y * index_layer.rasterUnitsPerPixelX()), 
                                        QgsRaster.IdentifyFormatValue)
                if result.isValid():
                    value = result.results()[1]
                    if value is not None:
                        values.append(value)

        if not values:
            print("Не знайдено жодного допустимого значення.")
            return

        plt.figure(figsize=(10, 6))
        plt.hist(values, bins=30, color='green', edgecolor='black', alpha=0.7, density=True, label='Гістограма')

        x = np.linspace(stats['min'], stats['max'], 50)
        mean, std_dev = stats['mean'], stats['std_dev']
        pdf = norm.pdf(x, loc=mean, scale=std_dev)
        plt.plot(x, pdf, 'r-', lw=2, label='Нормальний розподіл')

        plt.axvline(mean, color='b', linestyle='--', label='Середнє')
        plt.axvline(mean + std_dev, color='g', linestyle='--', label='+1 стандартне відхилення')
        plt.axvline(mean - std_dev, color='g', linestyle='--', label='-1 стандартне відхилення')

        plt.title(f"Розподіл значень для {index_layer.name()}")
        plt.xlabel("Значення індексу")
        plt.ylabel("Щільність ймовірності")
        plt.grid(True)
        plt.legend()

        plt.text(
            0.95, 0.95,
            f"Mean: {stats['mean']:.2f}\nMin: {stats['min']:.2f}\nMax: {stats['max']:.2f}\nStdDev: {stats['std_dev']:.2f}",
            ha='right', va='top', transform=plt.gca().transAxes,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.7)
        )

        plt.xlim(stats['min'], stats['max'])

        try:
            plt.savefig(output_path, format='png', dpi=300)
            plt.close()
            print(f"Гістограму успішно збережено в: {output_path}")
        except Exception as e:
            print(f"Помилка при збереженні гістограми: {e}")


    def create_color_scale(self, index_layer, index_stats, index_type):

        shader = QgsRasterShader()
        color_ramp = QgsColorRampShader()
        color_ramp.setColorRampType(QgsColorRampShader.Interpolated)

        min_val = index_stats["min"]
        max_val = index_stats["max"]
        mean_val = index_stats["mean"]
        std_dev = index_stats["std_dev"]

        if index_type == "NDVI":
            color_ramp.setColorRampItemList([
                QgsColorRampShader.ColorRampItem(
                    min_val, QColor(0, 0, 255), "Water"),
                QgsColorRampShader.ColorRampItem(
                    0, QColor(255, 255, 255), "Bare Soil"),
                QgsColorRampShader.ColorRampItem(
                    0.3, QColor(34, 139, 34), "Vegetation"),
                QgsColorRampShader.ColorRampItem(
                    max_val, QColor(0, 255, 0), "Max Vegetation")
            ])

        elif index_type == "EVI":
            color_ramp.setColorRampItemList([
                QgsColorRampShader.ColorRampItem(
                    min_val, QColor(0, 0, 255), "Water"),
                QgsColorRampShader.ColorRampItem(
                    0, QColor(255, 255, 255), "Bare Soil"),
                QgsColorRampShader.ColorRampItem(
                    0.2, QColor(255, 255, 0), "Low Vegetation"),
                QgsColorRampShader.ColorRampItem(
                    max_val, QColor(0, 255, 0), "Dense Vegetation")
            ])

        elif index_type == "GNDVI":
            color_ramp.setColorRampItemList([
                QgsColorRampShader.ColorRampItem(
                    min_val, QColor(0, 0, 255), "Water"),
                QgsColorRampShader.ColorRampItem(
                    0, QColor(255, 255, 255), "Bare Soil"),
                QgsColorRampShader.ColorRampItem(
                    0.2, QColor(34, 139, 34), "Vegetation"),
                QgsColorRampShader.ColorRampItem(
                    max_val, QColor(0, 255, 0), "Dense Vegetation")
            ])

        elif index_type == "CVI":
            color_ramp.setColorRampItemList([
                QgsColorRampShader.ColorRampItem(
                    min_val, QColor(255, 0, 0), "Low Chlorophyll"),
                QgsColorRampShader.ColorRampItem(
                    mean_val, QColor(255, 255, 0), "Medium Chlorophyll"),
                QgsColorRampShader.ColorRampItem(
                    max_val, QColor(0, 255, 0), "High Chlorophyll")
            ])

        shader.setRasterShaderFunction(color_ramp)

        renderer = QgsSingleBandPseudoColorRenderer(
            index_layer.dataProvider(),
            1,
            shader
        )
        index_layer.setRenderer(renderer)
        index_layer.triggerRepaint()


    def save_color_scale(self, index_layer, output_path):

        renderer = index_layer.renderer()
        shader = renderer.shader()

        if isinstance(shader.rasterShaderFunction(), QgsColorRampShader):
            color_ramp = shader.rasterShaderFunction()
            color_ramp_items = color_ramp.colorRampItemList()

            colors = []
            values = []

            for ramp_item in color_ramp_items:
                values.append(ramp_item.value)
                colors.append(ramp_item.color.name())

            from matplotlib.colors import ListedColormap, hex2color
            cmap = ListedColormap([hex2color(color) for color in colors])

            plt.figure(figsize=(10, 2))
            plt.imshow([range(len(colors))], cmap=cmap, aspect='auto')

            plt.title(f"Карта кольорів для {index_layer.name()}", fontsize=14, pad=30)

            plt.savefig(output_path, bbox_inches='tight', dpi=300)
            plt.close()


    def run(self):

        raster_layers = [layer for layer in self.iface.mapCanvas(
        ).layers() if isinstance(layer, QgsRasterLayer)]
        vector_layers = [layer for layer in self.iface.mapCanvas(
        ).layers() if isinstance(layer, QgsVectorLayer)]

        if not raster_layers and vector_layers:
            QMessageBox.warning(self.iface.mainWindow(),
                                "Помилка", "Не завантажено растрові та векторні шари!")
            return

        if len(raster_layers) < 4:
            QMessageBox.warning(self.iface.mainWindow(), "Error",
                                "Для отримання статистики потрібно щонайменше чотири растрових шари!")
            return

        else:
            QMessageBox.information(self.iface.mainWindow(
            ), "Info", f"Знайдено {len(raster_layers)} расторових та {len(vector_layers)} векторних шарів")
            ndvi_name, evi_name, gndvi_name, cvi_name, vector_name = self.choice_layers(
                raster_layers, vector_layers)

            ndvi_layer = QgsProject.instance().mapLayersByName(ndvi_name)[0]
            evi_layer = QgsProject.instance().mapLayersByName(evi_name)[0]
            gndvi_layer = QgsProject.instance().mapLayersByName(gndvi_name)[0]
            cvi_layer = QgsProject.instance().mapLayersByName(cvi_name)[0]
            vector_layer = QgsProject.instance(
            ).mapLayersByName(vector_name)[0]

            ndvi_stat = self.get_index_statistics(ndvi_layer)
            evi_stat = self.get_index_statistics(evi_layer)
            gndvi_stat = self.get_index_statistics(gndvi_layer)
            cvi_stat = self.get_index_statistics(cvi_layer)

            self.add_attributes(vector_layer, ndvi_layer, "ndvi_")
            self.add_attributes(vector_layer, evi_layer, "evi_")
            self.add_attributes(vector_layer, gndvi_layer, "gndvi_")
            self.add_attributes(vector_layer, cvi_layer, "cvi_")

            self.create_color_scale(ndvi_layer, ndvi_stat, "NDVI")
            self.create_color_scale(evi_layer, evi_stat, "EVI")
            self.create_color_scale(gndvi_layer, gndvi_stat, "GNDVI")
            self.create_color_scale(cvi_layer, cvi_stat, "CVI")

            output_path = QFileDialog.getSaveFileName(
                None, "Зберегти NDVi histogram", "", "*.png")[0]
            self.create_histogram(ndvi_layer, output_path)

            output_path = QFileDialog.getSaveFileName(
                None, "Зберегти EVI histogram", "", "*.png")[0]
            self.create_histogram(evi_layer, output_path)

            output_path = QFileDialog.getSaveFileName(
                None, "Зберегти GNDVI histogram", "", "*.png")[0]
            self.create_histogram(gndvi_layer, output_path)

            output_path = QFileDialog.getSaveFileName(
                None, "Зберегти CVI histogram", "", "*.png")[0]
            self.create_histogram(cvi_layer, output_path)

            output_path = QFileDialog.getSaveFileName(
                None, "Зберегти NDVI color scale", "", "*.png")[0]
            self.save_color_scale(ndvi_layer, output_path)

            output_path = QFileDialog.getSaveFileName(
                None, "Зберегти EVI color scale", "", "*.png")[0]
            self.save_color_scale(evi_layer, output_path)

            output_path = QFileDialog.getSaveFileName(
                None, "Зберегти GNDVI color scale", "", "*.png")[0]
            self.save_color_scale(gndvi_layer, output_path)

            output_path = QFileDialog.getSaveFileName(
                None, "Зберегти CVI color scale", "", "*.png")[0]
            self.save_color_scale(cvi_layer, output_path)


            QMessageBox.information(
                self.iface.mainWindow(), "Info", "Аналіз пройшов успішно!")