"""
Fenêtre principale de l'application Plan Légendage Amiante.

Ce module assemble tous les composants de l'interface :
- la barre d'outils (`Toolbar`)
- le panneau des planches (`PanneauPlanches`)
- le canvas de visualisation (`CanvasWidget`)
- le panneau Excel (`PanneauExcel`)

Il gère également les menus Fichier et Planches ainsi que les slots
de haut niveau (ouverture de fichiers, export PDF, gestion multi-planches).
"""

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
)

from src.models.planche import Planche
from src.services.excel_reader import charger_excel
from src.services.pdf_exporter import exporter_pdf
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

        # --- Données du projet ---------------------------------------------
        # Liste des planches ; la planche active est identifiée par son index
        self._planches: list[Planche] = []
        self._index_planche_active: int = -1

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
        self._panneau_excel.echantillon_selectionne.connect(self._canvas.definir_echantillon_actif)

        self._panneau_planches.planche_ajoutee.connect(self._ajouter_planche)
        self._panneau_planches.planche_supprimee.connect(self._supprimer_planche)
        self._panneau_planches.planche_selectionnee.connect(self._charger_planche)
        self._panneau_planches.planche_montee.connect(self._monter_planche)
        self._panneau_planches.planche_descendue.connect(self._descendre_planche)
        self._panneau_planches.planche_renommee.connect(self._renommer_planche)

        self._canvas.bulle_creee.connect(self._on_bulle_creee)

        # --- Raccourcis presse-papier --------------------------------------
        QShortcut(QKeySequence.StandardKey.Copy,  self).activated.connect(self._canvas.copier)
        QShortcut(QKeySequence.StandardKey.Cut,   self).activated.connect(self._canvas.couper)
        QShortcut(QKeySequence.StandardKey.Paste, self).activated.connect(self._canvas.coller)

        # --- Initialisation de la première planche -------------------------
        self._initialiser_premiere_planche()

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
        action_supprimer.triggered.connect(self._supprimer_planche_active)

        menu_planches.addSeparator()

        action_renommer = menu_planches.addAction("Renommer la planche")
        action_renommer.setStatusTip("Renommer la référence de la planche sélectionnée")
        action_renommer.triggered.connect(self._renommer_planche_active)

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _initialiser_premiere_planche(self) -> None:
        """Crée la planche initiale au démarrage de l'application."""
        planche = Planche(numero=1, reference_plan="Planche de repérage 01")
        self._planches.append(planche)
        self._panneau_planches.rafraichir(self._planches)
        self._panneau_planches.selectionner(0)
        self._index_planche_active = 0
        logger.info("Planche initiale créée.")

    # ------------------------------------------------------------------
    # Gestion de l'état canvas ↔ planche
    # ------------------------------------------------------------------

    def _sauvegarder_etat_canvas(self) -> None:
        """Sauvegarde l'état courant du canvas dans la planche active."""
        if self._index_planche_active < 0 or self._index_planche_active >= len(self._planches):
            return
        planche = self._planches[self._index_planche_active]
        etat = self._canvas.lire_etat()
        planche.plan_chemin  = etat["plan_chemin"]
        planche.plan_crop    = etat["plan_crop"]
        planche.formes       = etat["formes"]
        planche.bulles       = etat["bulles"]
        planche.zoom_factor  = etat["zoom_factor"]
        planche.offset       = etat["offset"]
        planche.zone_plan    = etat.get("zone_plan")

    def _charger_planche(self, index: int) -> None:
        """
        Sauvegarde la planche courante puis charge la planche à l'index donné.

        Paramètres
        ----------
        index : int
            Index de la planche à afficher dans la liste.
        """
        if index == self._index_planche_active:
            return
        self._sauvegarder_etat_canvas()
        self._index_planche_active = index
        planche = self._planches[index]
        self._canvas.appliquer_etat({
            "plan_chemin": planche.plan_chemin,
            "plan_crop":   planche.plan_crop,
            "formes":      planche.formes,
            "bulles":      planche.bulles,
            "zoom_factor": planche.zoom_factor,
            "offset":      planche.offset,
        })
        self._panneau_excel.definir_filtre_planche(planche.reference_plan)
        self._panneau_planches.selectionner(index)
        logger.info("Planche %d chargée.", planche.numero)

    # ------------------------------------------------------------------
    # Slots — gestion des planches
    # ------------------------------------------------------------------

    def _ajouter_planche(self) -> None:
        """Ajoute une nouvelle planche vide à la fin de la liste."""
        self._sauvegarder_etat_canvas()
        numero = len(self._planches) + 1
        planche = Planche(
            numero=numero,
            reference_plan=f"Planche de repérage {numero:02d}",
        )
        self._planches.append(planche)
        self._panneau_planches.rafraichir(self._planches)
        # Forcer le rechargement en réinitialisant l'index
        self._index_planche_active = -1
        self._charger_planche(len(self._planches) - 1)
        logger.info("Planche %d ajoutée.", numero)

    def _supprimer_planche(self, index: int) -> None:
        """
        Supprime la planche à l'index donné.

        Paramètres
        ----------
        index : int
            Index de la planche à supprimer dans la liste.
        """
        if len(self._planches) <= 1:
            QMessageBox.warning(
                self,
                "Suppression impossible",
                "Le projet doit contenir au moins une planche.",
            )
            return
        if index < 0 or index >= len(self._planches):
            return

        self._planches.pop(index)

        # Renuméroter les planches restantes
        for i, p in enumerate(self._planches):
            p.numero = i + 1

        self._panneau_planches.rafraichir(self._planches)
        nouvel_index = min(index, len(self._planches) - 1)
        self._index_planche_active = -1  # forcer le rechargement
        self._charger_planche(nouvel_index)
        logger.info("Planche supprimée ; nouvelle planche active : %d.", nouvel_index)

    def _supprimer_planche_active(self) -> None:
        """Supprime la planche actuellement active (invoqué depuis le menu)."""
        self._supprimer_planche(self._index_planche_active)

    def _monter_planche(self, index: int) -> None:
        """
        Remonte la planche d'un cran dans la liste.

        Paramètres
        ----------
        index : int
            Index actuel de la planche à remonter.
        """
        if index <= 0 or index >= len(self._planches):
            return
        self._sauvegarder_etat_canvas()
        self._planches[index], self._planches[index - 1] = (
            self._planches[index - 1],
            self._planches[index],
        )
        for i, p in enumerate(self._planches):
            p.numero = i + 1
        self._panneau_planches.rafraichir(self._planches)
        self._index_planche_active = -1
        self._charger_planche(index - 1)

    def _descendre_planche(self, index: int) -> None:
        """
        Descend la planche d'un cran dans la liste.

        Paramètres
        ----------
        index : int
            Index actuel de la planche à descendre.
        """
        if index < 0 or index >= len(self._planches) - 1:
            return
        self._sauvegarder_etat_canvas()
        self._planches[index], self._planches[index + 1] = (
            self._planches[index + 1],
            self._planches[index],
        )
        for i, p in enumerate(self._planches):
            p.numero = i + 1
        self._panneau_planches.rafraichir(self._planches)
        self._index_planche_active = -1
        self._charger_planche(index + 1)

    def _renommer_planche(self, index: int, nouveau_nom: str) -> None:
        """
        Met à jour la référence plan d'une planche après un double-clic dans le panneau.

        Paramètres
        ----------
        index : int
            Index de la planche à renommer.
        nouveau_nom : str
            Nouveau nom de référence.
        """
        if index < 0 or index >= len(self._planches):
            return
        self._planches[index].reference_plan = nouveau_nom
        self._panneau_planches.rafraichir(self._planches)
        self._panneau_planches.selectionner(index)
        # Mettre à jour le filtre Excel si la planche renommée est l'active
        if index == self._index_planche_active:
            self._panneau_excel.definir_filtre_planche(nouveau_nom)

    def _renommer_planche_active(self) -> None:
        """Lance le renommage de la planche active depuis le menu Planches."""
        from PyQt6.QtWidgets import QInputDialog
        index = self._index_planche_active
        if index < 0 or index >= len(self._planches):
            return
        nom_actuel = self._planches[index].reference_plan
        nouveau_nom, confirme = QInputDialog.getText(
            self,
            "Renommer la planche",
            "Nouveau nom de référence :",
            text=nom_actuel,
        )
        if confirme and nouveau_nom.strip():
            self._renommer_planche(index, nouveau_nom.strip())

    # ------------------------------------------------------------------
    # Slots — fichiers
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
            return

        try:
            echantillons = charger_excel(chemin)
            self._panneau_excel.charger_echantillons(echantillons)
            logger.info(
                "Excel chargé : %d échantillon(s) depuis '%s'.",
                len(echantillons),
                chemin,
            )
            if not echantillons:
                QMessageBox.warning(
                    self,
                    "Fichier vide",
                    "Aucun prélèvement trouvé dans la feuille « Prv Am ».\n"
                    "Vérifiez que la feuille existe et que la colonne G est renseignée.",
                )
        except Exception as exc:
            logger.error("Erreur chargement Excel : %s", exc)
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de lire le fichier :\n{exc}",
            )

    def _ouvrir_plan(self) -> None:
        """
        Ouvre une boîte de dialogue pour choisir un plan,
        puis l'affiche dans le canvas et mémorise le chemin dans la planche active.
        """
        chemin, _ = QFileDialog.getOpenFileName(
            self,
            "Ouvrir un plan",
            "",
            "Images et PDF (*.png *.jpg *.jpeg *.pdf)",
        )
        if not chemin:
            return

        self._canvas.charger_plan(chemin)
        # Mémoriser le chemin dans la planche active pour la sauvegarde d'état
        if 0 <= self._index_planche_active < len(self._planches):
            self._planches[self._index_planche_active].plan_chemin = chemin
        logger.info("Plan ouvert : %s", chemin)

    def _exporter_pdf(self) -> None:
        """
        Ouvre une boîte de dialogue pour choisir l'emplacement de sauvegarde,
        puis exporte toutes les planches dans un fichier PDF A4 paysage.
        """
        chemin, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter en PDF",
            "",
            "PDF (*.pdf)",
        )
        if not chemin:
            return

        # S'assurer que l'état du canvas est sauvegardé dans la planche active
        self._sauvegarder_etat_canvas()

        try:
            exporter_pdf(chemin, self._planches)
            logger.info("Export PDF réussi : %s", chemin)
            QMessageBox.information(
                self,
                "Export réussi",
                f"Le fichier PDF a été exporté avec succès :\n{chemin}",
            )
        except Exception as exc:
            logger.error("Erreur export PDF : %s", exc)
            QMessageBox.critical(
                self,
                "Erreur d'export",
                f"Impossible de générer le PDF :\n{exc}",
            )

    # ------------------------------------------------------------------
    # Slots — canvas
    # ------------------------------------------------------------------

    def _on_bulle_creee(self, bulle) -> None:
        """
        Slot appelé après la création d'une bulle call-out.

        L'échantillon est déjà lié à la bulle au moment de sa création
        (sélection préalable dans le panneau Excel obligatoire).

        Paramètres
        ----------
        bulle : BulleLegende
            La bulle créée, avec son échantillon déjà lié.
        """
        logger.info(
            "Bulle créée — prélèvement='%s' (id=%s).",
            bulle.echantillon.prelevement if bulle.echantillon else "—",
            bulle.id,
        )
