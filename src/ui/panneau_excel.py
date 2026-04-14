"""
Panneau latéral droit : gestion et affichage des échantillons Excel.

Ce module définit la classe `PanneauExcel` qui permet à l'utilisateur
d'ouvrir un fichier Excel et d'afficher la liste des échantillons qu'il
contient sous forme de lignes avec pastille colorée. La logique de lecture
du fichier est déléguée aux services. Le panneau propose un filtre par
référence de plan pour n'afficher que les échantillons de la planche active.
"""

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.utils.constantes import MARGE_PANNEAU

# Journalisation propre au module
logger = logging.getLogger(__name__)


class PanneauExcel(QWidget):
    """
    Panneau de gestion des échantillons issus d'un fichier Excel.

    Affiche la liste complète des échantillons chargés, avec pastille colorée
    et texte (prélèvement — localisation). Un bouton toggle permet de filtrer
    par référence de plan de la planche active.

    Signaux
    -------
    ouvrir_excel_demande : pyqtSignal()
        Émis lorsque l'utilisateur clique sur le bouton "Ouvrir Excel".
        La fenêtre principale se charge d'ouvrir la boîte de dialogue.
    echantillon_selectionne : pyqtSignal(object)
        Émis lorsque l'utilisateur clique sur un échantillon dans la liste.
        Transmet l'objet Echantillon sélectionné.
    """

    ouvrir_excel_demande = pyqtSignal()
    echantillon_selectionne = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # --- Données internes -----------------------------------------------
        # Liste complète de tous les échantillons chargés depuis l'Excel
        self._tous_echantillons: list = []
        # Référence plan de la planche active (chaîne vide = aucun filtre)
        self._filtre_planche: str = ""
        # True = afficher uniquement les échantillons de la planche active
        self._filtre_actif: bool = False
        # Échantillon actuellement sélectionné (None si aucun)
        self._echantillon_actif = None

        # --- Mise en page verticale -----------------------------------------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGE_PANNEAU, MARGE_PANNEAU, MARGE_PANNEAU, MARGE_PANNEAU)
        layout.setSpacing(MARGE_PANNEAU)

        # --- Ligne haute : bouton Ouvrir + toggle filtre --------------------
        layout_haut = QHBoxLayout()
        layout_haut.setSpacing(MARGE_PANNEAU)

        # Bouton d'ouverture du fichier Excel
        self._btn_ouvrir = QPushButton("Ouvrir Excel")
        self._btn_ouvrir.setToolTip("Ouvrir un fichier Excel contenant les échantillons")
        layout_haut.addWidget(self._btn_ouvrir)

        # Bouton toggle : afficher tous les échantillons ou filtrer par planche
        self._btn_filtre = QPushButton("Tous")
        self._btn_filtre.setCheckable(True)
        self._btn_filtre.setChecked(False)
        self._btn_filtre.setToolTip(
            "Tous : afficher tous les échantillons\n"
            "Planche : n'afficher que les échantillons de la planche active"
        )
        layout_haut.addWidget(self._btn_filtre)

        layout.addLayout(layout_haut)

        # --- Liste scrollable des échantillons ------------------------------
        self._liste = QListWidget()
        self._liste.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._liste.setToolTip("Liste des échantillons chargés depuis le fichier Excel")
        layout.addWidget(self._liste)

        # --- Connexions de signaux ------------------------------------------
        self._btn_ouvrir.clicked.connect(self.ouvrir_excel_demande)
        self._btn_filtre.toggled.connect(self._on_filtre_bascule)
        self._liste.itemClicked.connect(self._on_item_clique)

    # ------------------------------------------------------------------
    # Méthodes publiques
    # ------------------------------------------------------------------

    def charger_echantillons(self, echantillons: list) -> None:
        """
        Reçoit la liste complète des échantillons depuis main_window.
        Stocke et rafraîchit l'affichage immédiatement.

        Paramètres
        ----------
        echantillons : list
            Liste d'objets Echantillon à afficher.
        """
        self._tous_echantillons = echantillons
        self._rafraichir_liste()
        logger.info("%d échantillon(s) reçus dans le panneau Excel.", len(echantillons))

    def definir_filtre_planche(self, reference_plan: str) -> None:
        """
        Définit la référence plan pour le filtre et rafraîchit si le filtre
        est actif.

        Paramètres
        ----------
        reference_plan : str
            Référence du plan de la planche active (colonne O de l'Excel).
        """
        self._filtre_planche = reference_plan
        if self._filtre_actif:
            self._rafraichir_liste()

    # ------------------------------------------------------------------
    # Méthodes privées
    # ------------------------------------------------------------------

    def _rafraichir_liste(self) -> None:
        """Vide et repeuple le QListWidget selon le filtre actif."""
        self._liste.clear()
        for ech in self._echantillons_filtres():
            self._ajouter_ligne(ech)

    def _echantillons_filtres(self) -> list:
        """
        Retourne les échantillons à afficher selon le filtre.

        Si le filtre n'est pas actif ou si la référence plan est vide,
        tous les échantillons sont retournés.
        """
        if not self._filtre_actif or not self._filtre_planche:
            return self._tous_echantillons
        return [
            e for e in self._tous_echantillons
            if e.reference_plan == self._filtre_planche
        ]

    def _ajouter_ligne(self, ech) -> None:
        """
        Ajoute une ligne avec pastille colorée et texte dans le QListWidget.

        Chaque ligne est un widget custom composé d'une pastille colorée
        (12×12 px, cercle CSS) et d'un label texte (prélèvement — localisation).

        Paramètres
        ----------
        ech : Echantillon
            L'échantillon à représenter dans la liste.
        """
        item = QListWidgetItem(self._liste)

        # Widget contenant la pastille + le texte
        widget_ligne = QWidget()
        layout_h = QHBoxLayout(widget_ligne)
        layout_h.setContentsMargins(4, 2, 4, 2)
        layout_h.setSpacing(6)

        # Pastille couleur (12×12 px, cercle CSS)
        r, g, b = ech.couleur
        pastille = QLabel()
        pastille.setFixedSize(12, 12)
        pastille.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); "
            "border-radius: 6px; "
            "border: 1px solid rgba(0,0,0,0.3);"
        )

        # Texte : prélèvement — localisation
        texte = f"{ech.prelevement} — {ech.localisation}"
        label_texte = QLabel(texte)
        label_texte.setToolTip(
            f"Résultat : {ech.resultat}\n"
            f"Description : {ech.description}\n"
            f"Mention : {ech.mention}"
        )

        layout_h.addWidget(pastille)
        layout_h.addWidget(label_texte)
        layout_h.addStretch()

        # Associer l'échantillon à l'item pour récupération ultérieure
        item.setData(Qt.ItemDataRole.UserRole, ech)
        item.setSizeHint(widget_ligne.sizeHint())

        self._liste.addItem(item)
        self._liste.setItemWidget(item, widget_ligne)

    def _on_filtre_bascule(self, coche: bool) -> None:
        """
        Slot activé lors du basculement du bouton filtre.

        Met à jour l'état du filtre et rafraîchit la liste.
        Met à jour le texte du bouton pour refléter l'état actif.

        Paramètres
        ----------
        coche : bool
            True si le bouton est maintenant coché (filtre par planche actif).
        """
        self._filtre_actif = coche
        self._btn_filtre.setText("Planche" if coche else "Tous")
        self._rafraichir_liste()

    @property
    def echantillon_actif(self):
        """Retourne l'échantillon actuellement sélectionné, ou None."""
        return self._echantillon_actif

    def reinitialiser_selection(self) -> None:
        """Efface la sélection active (aucun échantillon sélectionné)."""
        self._echantillon_actif = None
        self._liste.clearSelection()

    def _on_item_clique(self, item: QListWidgetItem) -> None:
        """
        Slot activé lors du clic sur un item de la liste.

        Stocke l'échantillon sélectionné et émet le signal echantillon_selectionne.

        Paramètres
        ----------
        item : QListWidgetItem
            L'item cliqué dans la liste.
        """
        ech = item.data(Qt.ItemDataRole.UserRole)
        if ech is not None:
            self._echantillon_actif = ech
            self.echantillon_selectionne.emit(ech)
