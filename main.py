from qgis.PyQt.QtWidgets import QAction

from qgis.gui import QgisInterface

from .territory_analysis import TerritoryAnalysis
from .index_statistics import IndexStatistics
from .report_generator import NDVIReportGenerator
from .report_generator import EVIReportGenerator
from .report_generator import GNDVIReportGenerator
from .report_generator import CVIReportGenerator


class ButtonManager:

    plugin_name = '&Territory Analysis'
    actions: list[QAction] = list()

    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface

        self.ter_anal = TerritoryAnalysis(iface=iface)
        self.index_stat = IndexStatistics(iface=iface)
        self.rep_gen1 = NDVIReportGenerator(iface=iface)
        self.rep_gen2 = EVIReportGenerator(iface=iface)
        self.rep_gen3 = GNDVIReportGenerator(iface=iface)
        self.rep_gen4 = CVIReportGenerator(iface=iface)

    def initGui(self):
        self.actions.append(self.ter_anal.get_action())
        self.actions.append(self.index_stat.get_action())
        self.actions.append(self.rep_gen1.get_action())
        self.actions.append(self.rep_gen2.get_action())
        self.actions.append(self.rep_gen3.get_action())
        self.actions.append(self.rep_gen4.get_action())

        for action in self.actions:
            self.iface.addPluginToMenu(self.plugin_name, action)

    def unload(self):

        for action in self.actions:
            self.iface.removePluginMenu(self.plugin_name, action)
