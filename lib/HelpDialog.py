from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox
from help_content import HELP_TEXT


class HelpDialog(QDialog):
    """Scrollable in-app Help (Sync Modes + setup essentials)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help")
        self.resize(520, 560)

        layout = QVBoxLayout(self)
        browser = QTextBrowser(self)
        browser.setReadOnly(True)
        browser.setPlainText(HELP_TEXT)
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
