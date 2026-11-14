"""Validated PNG tile cache; independent of Kivy for regression tests."""
import os
import uuid
from pathlib import Path

PNG = b'\x89PNG\r\n\x1a\n'
PNG_END = b'IEND\xaeB`\x82'


class MapLoadError(Exception):
    pass


def valid_png(data):
    return len(data) >= 45 and data.startswith(PNG) and data.endswith(PNG_END)


class TileCache:
    def __init__(self, folder, get=None, ca_file=True):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.get = get
        self.ca_file = ca_file

    def fetch(self, url, filename):
        # Tile filenames come from MapView. Keep all writes in our cache root.
        if Path(filename).name != filename or filename in ('', '.', '..'):
            raise MapLoadError('Nome de imagem do mapa inválido.')
        target = self.folder / filename
        if target.exists() and valid_png(target.read_bytes()):
            return str(target)
        if not url.startswith('https://'):
            raise MapLoadError('O mapa precisa de uma conexão segura.')
        try:
            if self.get is None:
                from requests import get
            else:
                get = self.get
            response = get(url, headers={'User-Agent': 'PassoPython/2.0.1 (Android walking tracker)'},
                           timeout=(5, 12), verify=self.ca_file)
            response.raise_for_status()
            data = response.content
            if not valid_png(data):
                raise MapLoadError('O servidor não enviou uma imagem válida do mapa.')
            # Recreate the directory if Android/a cleanup removed it after startup.
            self.folder.mkdir(parents=True, exist_ok=True)
            temporary = self.folder / (filename + '.' + uuid.uuid4().hex + '.tmp')
            try:
                temporary.write_bytes(data)
                os.replace(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()
            return str(target)
        except MapLoadError:
            raise
        except Exception as exc:
            raise MapLoadError('Não foi possível carregar o mapa. Confira a internet e tente novamente.') from exc
