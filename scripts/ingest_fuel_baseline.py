"""Load a newer SENATRAN fuel spreadsheet or reviewed JSON into the official ruler."""
import argparse
from pathlib import Path
from src.connectors.fuel import ingest_fuel_file
from src.connectors.reviewed_sources import REVIEWED, seed_fuel

def main():
    parser = argparse.ArgumentParser(description='Atualiza a régua SENATRAN por combustível. Não altera a Frota por família.')
    parser.add_argument('--file', help='CSV/XLSX oficial de combustível')
    parser.add_argument('--reference', help='YYYY-MM da planilha')
    args = parser.parse_args()
    if args.file:
        if not args.reference:
            raise SystemExit('Informe --reference YYYY-MM junto com --file')
        result = ingest_fuel_file(args.file, args.reference)
        print(result)
        return
    inserted = seed_fuel()
    files = sorted(REVIEWED.glob('senatran-fuel-*.json')) if REVIEWED.exists() else []
    print({'seeded_rows': inserted, 'reviewed_files': [p.name for p in files],
           'note': 'Sem planilha nova, permanece o JSON revisado mais recente (hoje 2026-02).'})

if __name__ == '__main__':
    main()
