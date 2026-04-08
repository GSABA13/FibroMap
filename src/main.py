"""
Point d'entrée de l'application Plan Légendage Amiante.

Lance l'application PyQt6 et affiche la fenêtre principale.
"""

import logging
import sys

from PyQt6.QtWidgets import QApplication

from src.ui.main_window import MainWindow


def main() -> None:
    """Initialise et démarre l'application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s : %(message)s",
    )
    app = QApplication(sys.argv)
    fenetre = MainWindow()
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
