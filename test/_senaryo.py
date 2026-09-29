# Uçtan uca sınama için fiyatlar.json'u bozar/onarır. Kullanım: python test/_senaryo.py <ad>
import json, sys, os, shutil
from datetime import datetime, timedelta, timezone
k = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); hedef = os.path.join(k, "fiyatlar.json")
iyi = json.load(open(os.path.join(k, "test", "fiyatlar.iyi.json"), encoding="utf-8"))
ist = timezone(timedelta(hours=3)); ad = sys.argv[1]
def yaz(o): open(hedef, "w", encoding="utf-8").write(o if isinstance(o, str) else json.dumps(o, ensure_ascii=False))
if ad == "iyi": iyi["zaman"] = datetime.now(ist).isoformat(timespec="seconds"); yaz(iyi)
elif ad == "yok": os.path.exists(hedef) and os.remove(hedef)
elif ad == "cop": yaz("<html>Just a moment...</html>")
elif ad == "ters": iyi["has"] = {"alis": 6600, "satis": 6500}; yaz(iyi)
elif ad == "ileri": iyi["zaman"] = (datetime.now(ist) + timedelta(days=1)).isoformat(); yaz(iyi)
elif ad == "eski": iyi["zaman"] = (datetime.now(ist) - timedelta(hours=40)).isoformat(); yaz(iyi)
elif ad == "yan_bozuk": iyi["zaman"] = datetime.now(ist).isoformat(timespec="seconds"); iyi["ayar14"] = {"alis": 6500, "satis": 6559}; yaz(iyi)
elif ad == "devasa": yaz("[" + "1," * 80000 + "1]")
print("senaryo:", ad)
