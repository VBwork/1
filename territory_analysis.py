from qgis.PyQt.QtWidgets import QAction

from qgis.gui import QgisInterface

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
)

from qgis.analysis import (
    QgsRasterCalculator,
    QgsRasterCalculatorEntry,
)

from qgis.core import (
    Qgis,
    QgsProject,
    QgsRasterLayer,
)

from qgis.gui import (
    QgisInterface,
)

from qgis.PyQt.QtWidgets import (
    QAction,
    QFileDialog,
    QMessageBox,
)


class TerritoryAnalysis:
    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface

    def get_action(self) -> QAction:
        action = QAction('Index calculate', self.iface.mainWindow())
        action.setObjectName(" ")
        action.setWhatsThis(" ")
        action.setStatusTip(" ")
        action.triggered.connect(self.run)

        return action

    def choice_layers(self, layers):

        dialog = QDialog()
        dialog.setWindowTitle("Вибір спектрів")
        dialog.setFixedSize(300, 300)

        layout = QVBoxLayout()

        red_combo = QComboBox()
        for layer in layers:
            red_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("Червоний спектр (RED):"))
        layout.addWidget(red_combo)

        nir_combo = QComboBox()
        for layer in layers:
            nir_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("Ближній інфрачервоний спектр (NIR):"))
        layout.addWidget(nir_combo)

        blue_combo = QComboBox()
        for layer in layers:
            blue_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("Синій спектр (BLUE):"))
        layout.addWidget(blue_combo)

        green_combo = QComboBox()
        for layer in layers:
            green_combo.addItem(layer.name(), layer)
        layout.addWidget(QLabel("Зелений спектр (GREEN):"))
        layout.addWidget(green_combo)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)

        dialog.setLayout(layout)

        if dialog.exec_():
            return red_combo.currentText(), nir_combo.currentText(), blue_combo.currentText(), green_combo.currentText()
        return None

    def ndvi_calculate(self, red_layer, nir_layer):

        entries = []

        red = QgsRasterCalculatorEntry()
        red.ref = f"{red_layer.name()}@1"
        red.raster = red_layer
        red.bandNumber = 1
        entries.append(red)

        nir = QgsRasterCalculatorEntry()
        nir.ref = f"{nir_layer.name()}@1"
        nir.raster = nir_layer
        nir.bandNumber = 1
        entries.append(nir)

        formula = f"({nir.ref} - {red.ref}) / ({nir.ref} + {red.ref})"

        output_path = QFileDialog.getSaveFileName(
            None, "Зберегти NDVI Calculate", "", "*.tif")[0]

        if not output_path:
            self.iface.messageBar().pushMessage(
                "Помилка", "Не вибрано вихідний шлях.")
            return

        else:
            calculator = QgsRasterCalculator(formula, output_path, "GTiff", red_layer.extent(
            ), red_layer.width(), red_layer.height(), entries)
            calculator.processCalculation()
            QMessageBox.information(self.iface.mainWindow(
            ), "Info", "Розрахунок пройшов успішно")
            self.add_result_to_project(output_path, "NDVI_Result")

    def evi_calculate(self, red_layer, nir_layer, blue_layer):

        G = 2.5
        C1 = 6
        C2 = 7.5
        L = 1

        entries = []

        red = QgsRasterCalculatorEntry()
        red.ref = f"{red_layer.name()}@1"
        red.raster = red_layer
        red.bandNumber = 1
        entries.append(red)

        nir = QgsRasterCalculatorEntry()
        nir.ref = f"{nir_layer.name()}@1"
        nir.raster = nir_layer
        nir.bandNumber = 1
        entries.append(nir)

        blue = QgsRasterCalculatorEntry()
        blue.ref = f"{blue_layer.name()}@1"
        blue.raster = blue_layer
        blue.bandNumber = 1
        entries.append(blue)

        formula = f"({G}* ({nir.ref} - {red.ref}) / ({nir.ref} + {C1} * {red.ref} - {C2} * {blue.ref} + {L}))"

        output_path = QFileDialog.getSaveFileName(
            None, "Зберегти EVI Calculate", "", "*.tif")[0]

        if not output_path:
            self.iface.messageBar().pushMessage(
                "Помилка", "Не вибрано вихідний шлях.", level=Qgis.Critical)
            return

        else:
            calculator = QgsRasterCalculator(formula, output_path, "GTiff", red_layer.extent(
            ), red_layer.width(), red_layer.height(), entries)
            calculator.processCalculation()
            QMessageBox.information(self.iface.mainWindow(
            ), "Info", "Розрахунок пройшов успішно")
            self.add_result_to_project(output_path, "EVI_Result")

    def gndvi_calculate(self, nir_layer, green_layer):

        entries = []

        nir = QgsRasterCalculatorEntry()
        nir.ref = f"{nir_layer.name()}@1"
        nir.raster = nir_layer
        nir.bandNumber = 1
        entries.append(nir)

        green = QgsRasterCalculatorEntry()
        green.ref = f"{green_layer.name()}@1"
        green.raster = green_layer
        green.bandNumber = 1
        entries.append(green)

        formula = f"({nir.ref} - {green.ref}) / ({nir.ref} + {green.ref})"

        output_path = QFileDialog.getSaveFileName(
            None, "Зберегти GNDVI Calculate", "", "*.tif")[0]

        if not output_path:
            self.iface.messageBar().pushMessage(
                "Помилка", "Не вибрано вихідний шлях.", level=Qgis.Critical)
            return

        else:
            calculator = QgsRasterCalculator(formula, output_path, "GTiff", green_layer.extent(
            ), green_layer.width(), green_layer.height(), entries)
            calculator.processCalculation()
            QMessageBox.information(self.iface.mainWindow(
            ), "Info", "Розрахунок пройшов успішно")
            self.add_result_to_project(output_path, "GNDVI_Result")

    def cvi_calculate(self, red_layer, nir_layer, green_layer):

        entries = []

        red = QgsRasterCalculatorEntry()
        red.ref = f"{red_layer.name()}@1"
        red.raster = red_layer
        red.bandNumber = 1
        entries.append(red)

        nir = QgsRasterCalculatorEntry()
        nir.ref = f"{nir_layer.name()}@1"
        nir.raster = nir_layer
        nir.bandNumber = 1
        entries.append(nir)

        green = QgsRasterCalculatorEntry()
        green.ref = f"{green_layer.name()}@1"
        green.raster = green_layer
        green.bandNumber = 1
        entries.append(green)

        formula = f"({nir.ref} * {red.ref}) / ({red.ref} * {green.ref})"

        output_path = QFileDialog.getSaveFileName(
            None, "Зберегти CVI Calculate", "", "*.tif")[0]

        if not output_path:
            self.iface.messageBar().pushMessage(
                "Помилка", "Не вибрано вихідний шлях.", level=Qgis.Critical)
            return

        else:
            calculator = QgsRasterCalculator(formula, output_path, "GTiff", red_layer.extent(
            ), red_layer.width(), red_layer.height(), entries)
            calculator.processCalculation()
            QMessageBox.information(self.iface.mainWindow(
            ), "Info", "Розрахунок пройшов успішно")
            self.add_result_to_project(output_path, "CVI_Result")

    def add_result_to_project(self, output_path, layer_name):

        layers = QgsRasterLayer(output_path, layer_name)

        if layers.isValid():
            QgsProject.instance().addMapLayer(layers)
            self.iface.messageBar().pushMessage(
                "Успіх", f"{layer_name} додано до проекту.", level=Qgis.Info)

        else:
            self.iface.messageBar().pushMessage(
                "Помилка", f"Не вдалося завантажити {layer_name}.", level=Qgis.Critical)

    def run(self):

        layers = [layer for layer in self.iface.mapCanvas(
        ).layers() if isinstance(layer, QgsRasterLayer)]

        if not layers:
            QMessageBox.warning(self.iface.mainWindow(),
                                "Помилка", "Растрові шари не завантажено!")
            return

        if len(layers) < 2:
            QMessageBox.warning(self.iface.mainWindow(), "Помилка",
                                "Для розрахунку індексів потрібно щонайменше два растрових шари")
            return

        else:
            QMessageBox.information(self.iface.mainWindow(
            ), "Info", f"Знайдено {len(layers)} растрових шарів")
            red_name, nir_name, blue_name, green_name = self.choice_layers(
                layers)

            red_layer = QgsProject.instance().mapLayersByName(red_name)[0]
            nir_layer = QgsProject.instance().mapLayersByName(nir_name)[0]
            blue_layer = QgsProject.instance().mapLayersByName(blue_name)[0]
            green_layer = QgsProject.instance().mapLayersByName(green_name)[0]

            if red_layer and nir_layer:
                self.ndvi_calculate(red_layer, nir_layer)

            if red_layer and nir_layer and blue_layer:
                self.evi_calculate(red_layer, nir_layer, blue_layer)

            if nir_layer and green_layer:
                self.gndvi_calculate(nir_layer, green_layer)

            if nir_layer and red_layer and green_layer:
                self.cvi_calculate(red_layer, nir_layer, green_layer)