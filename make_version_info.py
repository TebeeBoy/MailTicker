"""Az exe Windows-os „Tulajdonságok → Részletek” adatait állítja elő PyInstallerhez."""
import os
import sys

from version import VERSION

TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(filevers={tup}, prodvers={tup}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040E04B0', [
      StringStruct('ProductName', 'Mail Ticker'),
      StringStruct('FileDescription', 'Mail Ticker – Gmail értesítősáv'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('ProductVersion', '{ver}'),
      StringStruct('OriginalFilename', 'MailTicker.exe'),
      StringStruct('InternalName', 'MailTicker')])]),
    VarFileInfo([VarStruct('Translation', [0x040E, 1200])])
  ]
)
"""

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join("build", "version_info.txt")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    parts = tuple(int(p) for p in VERSION.split(".")) + (0,) * (4 - len(VERSION.split(".")))
    with open(out, "w", encoding="utf-8") as f:
        f.write(TEMPLATE.format(tup=parts, ver=VERSION))
