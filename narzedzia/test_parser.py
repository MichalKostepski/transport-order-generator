import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from driver_parser import parse_driver_text

sample = """Kierowca: Jan Testowy
Dowód: ABC 123456
PESEL: 00000000000
Auto: RTA 12345
Naczepa: RTA 54321
Tel: 500 600 700"""

result = parse_driver_text(sample)
assert result["full_name"] == "Jan Testowy"
assert result["pesel"] == "00000000000"
assert result["truck_registration"] == "RTA 12345"
assert result["trailer_registration"] == "RTA 54321"
assert result["phone"] == "500 600 700"
print("Parser OK:", result)
