"""
Fenêtre principale de l'application Plan Légendage Amiante.

Ce module assemble tous les composants de l'interface :
- la barre d'outils (`Toolbar`)
- le panneau des planches (`PanneauPlanches`)
- le canvas de visualisation (`CanvasWidget`)
- le panneau Excel (`PanneauExcel`)

Il gère également les menus Fichier et Planches ainsi que les slots
de haut niveau (ouverture de fichiers, export PDF).
"""

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
)

from src.ui.canvas_widget import CanvasWidget
from src.ui.panneau_excel import PanneauExcel
from src.ui.panneau_planches import PanneauPlanches
from src.ui.toolbar import Toolbar
from src.utils.constantes import (
    HAUTEUR_FENETRE,
    LARGEUR_FENETRE,
    LARGEUR_PANNEAU_EXCEL,
    LARGEUR_PANNEAU_PLANCHES,
)

# Journalisation propre au module
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Fenêtre principale de l'application.

    Elle orchestre les widgets enfants, les menus et les connexions
    de signaux. Aucune logique métier n'est présente ici.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Plan Légendage Amiante")
        self.resize(LARGEUR_FENETRE, HAUTEUR_FENETRE)

        # --- Création des composants principaux ----------------------------
        self._toolbar = Toolbar(self)
        self._canvas = CanvasWidget(self)
        self._panneau_planches = PanneauPlanches(self)
        self._panneau_excel = PanneauExcel(self)

        # --- Barre d'outils ------------------------------------------------
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._toolbar)

        # --- Splitter horizontal (layout central) --------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._panneau_planches)
        splitter.addWidget(self._canvas)
        splitter.addWidget(self._panneau_excel)

        # Tailles initiales : panneau gauche | canvas (stretch) | panneau droit
        splitter.setSizes(
            [LARGEUR_PANNEAU_PLANCHES, LARGEUR_FENETRE, LARGEUR_PANNEAU_EXCEL]
        )
        splitter.setStretchFactor(1, 1)  # le canvas prend tout l'espace disponible

        self.setCentralWidget(splitter)

        # --- Menus ---------------------------------------------------------
        self._creer_menus()

        # --- Connexions de signaux -----------------------------------------
        self._toolbar.mode_change.connect(self._canvas.changer_mode)
        self._toolbar.transparence_change.connect(self._canvas.changer_transparence)
        self._toolbar.zoom_in.connect(self._canvas.zoom_in)
        self._toolbar.zoom_out.connect(self._canvas.zoom_out)
        self._toolbar.zoom_reset.connect(self._canvas.zoom_reset)
        self._toolbar.couleur_change.connect(self._canvas.changer_couleur_active)
        self._panneau_excel.ouvrir_excel_demande.connect(self._ouvrir_excel)
        self._panneau_planches.planche_ajoutee.connect(self._ajouter_planche)
        self._panneau_planches.planche_supprimee.connect(self._supprimer_planche)

    # ------------------------------------------------------------------
    # Construction des menus
    # ------------------------------------------------------------------

    def _creer_menus(self) -> None:
        """Construit la barre de menus de la fenêtre principale."""
        barre = self.menuBar()

        # --- Menu Fichier --------------------------------------------------
        menu_fichier = barre.addMenu("Fichier")

        action_ouvrir_excel = menu_fichier.addAction("Ouvrir Excel")
        action_ouvrir_excel.setShortcut("Ctrl+O")
        action_ouvrir_excel.setStatusTip("Ouvrir un fichier Excel contenant les échantillons")
        action_ouvrir_excel.triggered.connect(self._ouvrir_excel)

        action_ouvrir_plan = menu_fichier.addAction("Ouvrir Plan")
        action_ouvrir_plan.setStatusTip("Ouvrir un plan image (JPG, PNG) ou PDF")
        action_ouvrir_plan.triggered.connect(self._ouvrir_plan)

        # Action de réinitialisation du rognage (après "Ouvrir Plan")
        action_reset_rognage = QAction("Réinitialiser le rognage", self)
        action_reset_rognage.setStatusTip("Supprime le rognage et affiche le plan entier")
        action_reset_rognage.triggered.connect(self._canvas.reinitialiser_rognage)
        menu_fichier.addAction(action_reset_rognage)

        menu_fichier.addSeparator()

        action_exporter = menu_fichier.addAction("Exporter PDF")
        action_exporter.setShortcut("Ctrl+E")
        action_exporter.setStatusTip("Exporter le plan légendé au format PDF")
        action_exporter.triggered.connect(self._exporter_pdf)

        # --- Menu Planches -------------------------------------------------
        menu_planches = barre.addMenu("Planches")

        action_ajouter = menu_planches.addAction("Ajouter planche")
        action_ajouter.setStatusTip("Ajouter une nouvelle planche au projet")
        action_ajouter.triggered.connect(self._ajouter_planche)

        action_supprimer = menu_planches.addAction("Supprimer planche")
        action_supprimer.setStatusTip("Supprimer la planche sélectionnée")
        action_supprimer.triggered.connect(self._supprimer_planche)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _ouvrir_excel(self) -> None:
        """
        Ouvre une boîte de dialogue pour choisir un fichier Excel,
        puis charge les échantillons via le service et met à jour le panneau.
        """
        chemin, _ = QFileDialog.getOpenFileName(
            self,
            "Ouvrir un fichier Excel",
            "",
            "Fichiers Excel (*.xlsx *.xlsm *.xls)",
        )
        if not chemin:
            # L'utilisateur a annulé
            return

        # TODO : appeler charger_excel(chemin) depuis src/services/
        # echantillons = charger_excel(chemin)
        echantillons: list = []  # temporaire jusqu'à l'implémentation du service

        self._panneau_excel.charger_echantillons(echantillons)

    def _ouvrir_plan(self) -> None:
        """
        Ouvre une boîte de dialogue pour choisir un fichier plan,
        puis l'affiche dans le canvas.
        """
        chemin, _ = QFileDialog.getOpenFileName(
            self,
            "Ouvrir un plan",
            "",
            "Images et PDF (*.png *.jpg *.jpeg *.pdf)",
        )
        if not chemin:
            # L'utilisateur a annulé
            return

        self._canvas.charger_plan(chemin)
        logger.info("Plan ouvert : %s", chemin)

    def _exporter_pdf(self) -> None:
        """Exporte le plan légendé au format PDF (non implémenté)."""
        QMessageBox.information(
            self,
            "Export PDF",
            "Non implémenté",
        )

    def _ajouter_planche(self) -> None:
        """Ajoute une nouvelle planche (corps vide — à implémenter)."""
        # TODO : implémenter la logique d'ajout de planche
        pass  # noqa: PIE790

    def _supprimer_planche(self) -> None:
        """Supprime la planche sélectionnée (corps vide — à implémenter)."""
        # TODO : implémenter la logique de suppression de planche
        pass  # noqa: PIE790
