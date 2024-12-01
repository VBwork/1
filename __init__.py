from qgis.gui import QgisInterface


def classFactory(iface: QgisInterface):
    from .main import ButtonManager
    return ButtonManager(iface)