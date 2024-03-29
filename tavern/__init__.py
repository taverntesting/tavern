"""Stop pytest warning about module already imported: PYTEST_DONT_REWRITE"""

# At the very top of your "{your_package}.__init__" submodule:
from warnings import filterwarnings

from beartype.claw import beartype_this_package  # <-- boilerplate for victory
from beartype.roar import BeartypeDecorHintPep585DeprecationWarning

beartype_this_package()  # <-- yay! your team just won

filterwarnings("ignore", category=BeartypeDecorHintPep585DeprecationWarning)
__version__ = "2.10.1"
