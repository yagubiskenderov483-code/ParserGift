# Entrypoint wrapper — hosts that still run `python main.py` get the new app.
from app import main

if __name__ == "__main__":
    main()
