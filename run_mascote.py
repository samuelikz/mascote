# Entrada do PyInstaller: __main__.py usa imports relativos e não roda como script solto.
import sys

from mascote.__main__ import main

sys.exit(main())
