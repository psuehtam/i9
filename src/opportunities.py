"""Read-only real and simulated battery opportunity views."""
import hashlib
import heapq
from bisect import bisect_left
from collections import defaultdict
from datetime import date

from sqlalchemy import and_, func, select

from src import intelligence_schema as s, operational_schema as o
from src.battery_passport import FIELDS


def _fraction(key):
    return int(hashlib.sha256(str(key).encode()).hexdigest()[:12], 16) / 0xFFFFFFFFFFFF


def simulated_profile(vehicle, model, locations=()):
    """Stable, non-persisted demonstration profile for one registry vehicle."""
    vid = vehicle['id']
    year_simulated = not bool(vehicle.get('manufacture_year'))
    simulated_year = vehicle.get('manufacture_year') or (2015 + int(_fraction('year:' + vid) * 11))
    vehicle = {**vehicle, 'manufacture_year': simulated_year}
    model_key = '|'.join(str(model.get(k) or vehicle.get(k) or '') for k in
                         ('manufacturer', 'model', 'trim', 'manufacture_year', 'powertrain_type', 'vehicle_category'))
    family = _fraction('family:' + model_key)
    unit = _fraction('unit:' + vid)
    age = max(0, date.today().year - (vehicle.get('manufacture_year') or 2020))
    category = model.get('vehicle_category') or 'unknown'
    powertrain = model.get('powertrain_type') or 'UNKNOWN'
    if powertrain.startswith('MHEV'):
        capacity = round(0.4 + family * 0.8, 2)
    elif powertrain.startswith('HEV'):
        capacity = round(1.0 + family * 1.8, 2)
    elif powertrain == 'PHEV':
        capacity = round(12 + family * 28, 1)
    else:
        capacity = round((90 if category in ('bus', 'truck') else 30) + family * (240 if category in ('bus', 'truck') else 75), 1)
    chemistry = 'LFP' if family < 0.52 else 'NMC'
    # Scenario inspired by Geotab cohort findings; never a measured or fitted SOH.
    annual_loss = 1.4 + family * 1.6
    soh = round(max(55, min(100, 100 - age * annual_loss - unit * 12)), 1)
    cycles = int(age * (75 + 210 * unit))
    city = vehicle.get('municipality')
    state = vehicle.get('state')
    simulated_location = False
    if not city and locations:
        if isinstance(locations, dict):
            marker = _fraction('location:' + vid) * locations['total']
            index = min(len(locations['rows']) - 1, bisect_left(locations['cumulative'], marker))
            state, city = locations['rows'][index]
        else:
            index = min(len(locations) - 1, int(_fraction('location:' + vid) * len(locations)))
            state, city = locations[index][:2]
        simulated_location = True
    values = {}
    dynamic = {'61': str(soh), '62': str(soh), '67': 'Em uso no veículo', '68': str(cycles),
               '70': str(round(20 + 18 * unit, 1)), '71': str(round(20 + 60 * unit, 1))}
    voltage = round(300 + family * 450)
    power = round(capacity * (1.8 + unit), 1)
    resistance = round(30 + 35 * unit, 1)
    efficiency = round(92 + 4 * family, 1)
    known = {'1': 'SIM-' + vid[:18], '2': 'NEXUS — simulação', '3': model.get('manufacturer') or 'Fabricante simulado',
             '4': 'Endereço simulado — Brasil', '5': 'Contato digital simulado', '6': 'EV' if powertrain=='BEV' else 'Bateria de veículo híbrido',
             '7': 'PACK-' + hashlib.sha256(vid.encode()).hexdigest()[:12].upper(), '8': 'Planta simulada BR-01',
             '9': str(vehicle.get('manufacture_year') or 2020) + '-06', '10': str(round(capacity * 6.5, 1)) + ' kg',
             '11': str(capacity) + ' kWh', '12': chemistry, '13': 'Eletrólito inflamável — cenário',
             '14': 'Agente apropriado conforme protocolo simulado de emergência',
             '15': 'Lítio, grafite' + (', níquel, cobalto' if chemistry=='NMC' else ', ferro, fosfato'),
             '16': chemistry + ' / grafite / eletrólito orgânico', '17': str(round(capacity*75))+' kg CO₂e — simulado',
             '18': 'Classe simulada B', '19': 'Declaração simulada de fornecimento responsável',
             '20': '4%', '21': '3%', '22': '5%' if chemistry=='NMC' else '0%', '23': '0%', '24': '0%',
             '25': str(round(capacity*1000/voltage,1))+' Ah', '26': str(round(voltage*0.8))+' V',
             '27': str(voltage)+' V', '28': str(round(voltage*1.15))+' V', '29': str(round(power*1000))+' W',
             '30': f'0 a {round(power*1000)} W, 0–40 °C', '31': str(round(1200+family*2000))+' ciclos',
             '32': 'Teste simulado a 25 °C e 1 C', '33': '80% de SOH — cenário',
             '34': '-20 a 45 °C', '35': '8 anos', '36': str(efficiency)+'%',
             '37': str(round(efficiency-1.2,1))+'%', '38': str(resistance)+' mΩ',
             '39': '1 C', '43': 'Entrega a reciclador autorizado — orientação simulada',
             '44': 'Manual de uso simulado: evitar dano físico e calor excessivo',
             '45': chemistry+' / ânodo grafite / eletrólito orgânico',
             '46': 'MOD-'+hashlib.sha256(model_key.encode()).hexdigest()[:8].upper(),
             '47': 'Contato de reposição simulado', '48': 'Diagrama e sequência de desmontagem simulados',
             '49': 'Desenergizar e isolar o pack antes da intervenção — cenário',
             '50': 'Laudo simulado; não é certificado de conformidade',
             '51': str(round(capacity*soh/100,2))+' kWh', '52': str(round(100-soh,1))+'%',
             '53': str(round(power*soh*10))+' W', '54': str(round(100-soh,1))+'%',
             '55': str(round(resistance*(1+(100-soh)/100),1))+' mΩ',
             '56': str(round(100-soh,1))+'%', '57': str(round(efficiency-(100-soh)*0.08,1))+'%',
             '58': str(round((100-soh)*0.08,1))+' ponto percentual',
             '59': str(max(0,round(1200+family*2000)-cycles))+' ciclos restantes — cenário',
             '60': str(round(max(0,(soh-80)/annual_loss),1))+' anos até 80% — cenário',
             '63': str(round(soh-1,1))+'%', '64': str(round(efficiency-(100-soh)*0.08,1))+'%',
             '65': 'Autodescarga simulada de '+str(round(1+unit,1))+'% ao mês',
             '66': str(round(resistance*(1+(100-soh)/100),1))+' mΩ',
             '69': 'Nenhum evento adverso simulado',
             '70': str(round(20+18*unit,1))+' °C — última amostra simulada',
             '71': str(round(20+60*unit,1))+'% — última amostra simulada'}
    known.update(dynamic)
    for field in FIELDS:
        fid = field['id']
        if fid in known:
            values[fid] = {'value': known[fid], 'status': 'confirmed', 'source': 'SIMULAÇÃO — cenário NEXUS', 'reason': ''}
        elif fid in {'40', '41', '42'}:
            values[fid] = {'value': None, 'status': 'not_applicable', 'source': 'SIMULAÇÃO — cenário NEXUS',
                           'reason': 'Documento regulatório não usado nesta demonstração brasileira.'}
        else:
            values[fid] = {'value': 'Parâmetro simulado: ' + field['label'].lower(), 'status': 'confirmed',
                           'source': 'SIMULAÇÃO — cenário NEXUS', 'reason': ''}
    return {'id': vid, 'vehicle_id': vid, 'battery_id': 'sim-battery-' + vid,
            'manufacture_year': simulated_year, 'year_simulated': year_simulated,
            'capacity_kwh': capacity, 'chemistry': chemistry, 'soh_percent': soh, 'cycle_count': cycles,
            'annual_degradation_pct': round(annual_loss, 2), 'state': state, 'municipality': city,
            'location_simulated': simulated_location, 'passport': {'fields': FIELDS, 'values': values,
            'counts': {'confirmed': len(FIELDS)-3, 'not_applicable': 3, 'pending': 0, 'draft': 0, 'total': len(FIELDS)}},
            'source': 'SIMULAÇÃO — referência de tendências Geotab; perfil sintético, sem medição real'}


def status(soh, threshold, previous=None, latest_at=None):
    if soh is None:
        return {'status': 'insufficient', 'reason': 'Saúde da bateria não medida', 'distance_pct': None,
                'trend_pct': None, 'threshold_pct': threshold}
    distance = round(soh - threshold, 1)
    trend = round(soh - previous, 1) if previous is not None else None
    if latest_at and (date.today() - date.fromisoformat(str(latest_at)[:10])).days > 365:
        label = 'stale'
    else:
        label = 'priority' if distance <= 0 else 'near' if distance <= 5 else 'monitor'
    return {'status': label, 'reason': f'SOH {soh:.1f}% − limite {threshold:.1f}% = {distance:+.1f} pontos',
            'distance_pct': distance, 'trend_pct': trend, 'threshold_pct': threshold}


def real_rows(c, reference=None, state=None, municipality=None, category=None, powertrain=None, model=None, limit=50, offset=0, threshold=80):
    # Identified vehicles only. Statistical placeholders never become real opportunities.
    q = select(s.vehicle_asset, o.registry.c.public_code, o.model.c.model.label('registry_model'),
               o.model.c.manufacturer.label('registry_manufacturer'), s.battery_asset.c.id.label('battery_id'),
               s.battery_asset.c.soh_percent, s.battery_asset.c.last_observed_at, s.battery_asset.c.cycle_count).select_from(
        s.vehicle_asset.join(o.registry, o.registry.c.vehicle_id == s.vehicle_asset.c.id)
        .join(o.model, o.model.c.id == o.registry.c.current_model_id)
        .join(o.current_install, o.current_install.c.vehicle_id == s.vehicle_asset.c.id)
        .join(s.battery_asset, s.battery_asset.c.id == o.current_install.c.battery_id)).where(
            o.registry.c.visible.is_(True), s.vehicle_asset.c.identity_status.in_(['identified', 'verified']))
    if reference:
        q = q.join(s.fleet_unit_membership, s.fleet_unit_membership.c.vehicle_id == s.vehicle_asset.c.id).join(
            s.fleet_publication, s.fleet_publication.c.id == s.fleet_unit_membership.c.publication_id).where(
            s.fleet_publication.c.reference_period == reference)
    for col, val in ((s.vehicle_asset.c.state, state), (s.vehicle_asset.c.municipality, municipality),
                     (o.model.c.vehicle_category, category), (o.model.c.powertrain_type, powertrain)):
        if val: q = q.where(col == val)
    if model: q = q.where(o.model.c.model.ilike('%' + model + '%'))
    output = []
    for row in c.execute(q).mappings():
        item = dict(row)
        latest = c.execute(select(s.lifecycle.c.soh_percent, s.lifecycle.c.observed_at).where(
            s.lifecycle.c.battery_id == item['battery_id'], s.lifecycle.c.soh_percent.is_not(None))
            .order_by(s.lifecycle.c.observed_at.desc()).limit(2)).all()
        soh = latest[0][0] if latest else item.get('soh_percent')
        observed = latest[0][1] if latest else item.get('last_observed_at')
        previous = latest[1][0] if len(latest) > 1 else None
        item.update(status(soh, threshold, previous, observed))
        item['soh_percent'] = soh
        item['observed_at'] = observed
        output.append(item)
    order = {'priority': 0, 'near': 1, 'monitor': 2, 'stale': 3, 'insufficient': 4}
    output.sort(key=lambda x: (order[x['status']], x['distance_pct'] if x['distance_pct'] is not None else 999, x['id']))
    return {'items': output[offset:offset + limit], 'total': len(output), 'limit': limit, 'offset': offset}


def simulated_rows(c, reference=None, state=None, municipality=None, category=None, powertrain=None, model=None, limit=50, offset=0, threshold=80):
    q = select(s.vehicle_asset, o.registry.c.public_code, o.model.c.model.label('registry_model'),
               o.model.c.manufacturer.label('registry_manufacturer'), o.model.c.vehicle_category.label('registry_category'),
               o.model.c.powertrain_type.label('registry_powertrain')).select_from(
        s.vehicle_asset.join(o.registry, o.registry.c.vehicle_id == s.vehicle_asset.c.id)
        .join(o.model, o.model.c.id == o.registry.c.current_model_id)).where(o.registry.c.visible.is_(True))
    if reference:
        q = q.join(s.fleet_unit_membership, s.fleet_unit_membership.c.vehicle_id == s.vehicle_asset.c.id).join(
            s.fleet_publication, s.fleet_publication.c.id == s.fleet_unit_membership.c.publication_id).where(
            s.fleet_publication.c.reference_period == reference)
    if category: q = q.where(o.model.c.vehicle_category == category)
    if powertrain: q = q.where(o.model.c.powertrain_type == powertrain)
    if model: q = q.where(o.model.c.model.ilike('%' + model + '%'))
    locations = location_weights(c)
    count = [0]
    def candidates():
      for row in c.execute(q).mappings():
        item = dict(row)
        profile = simulated_profile(item, {'manufacturer': item['registry_manufacturer'], 'model': item['registry_model'],
            'powertrain_type': item['registry_powertrain'], 'vehicle_category': item['registry_category']}, locations)
        if state and profile['state'] != state: continue
        if municipality and profile['municipality'] != municipality: continue
        item.update(profile)
        item.update(status(profile['soh_percent'], threshold))
        item['observed_at'] = date.today().isoformat()
        item.pop('passport')
        count[0] += 1
        yield item
    order = {'priority': 0, 'near': 1, 'monitor': 2}
    output=heapq.nsmallest(offset+limit,candidates(),key=lambda x:(order[x['status']],x['distance_pct'],x['id']))
    return {'items': output[offset:offset + limit], 'total': count[0], 'limit': limit, 'offset': offset}


def location_weights(c):
    """Municipal distribution from the latest aggregate reference, for simulation only."""
    latest = c.execute(select(func.max(s.aggregate.c.reference_period))).scalar()
    if not latest:
        return []
    weighted = [tuple(row) for row in c.execute(select(s.aggregate.c.state, s.aggregate.c.municipality,
        func.sum(s.aggregate.c.quantity)).where(s.aggregate.c.reference_period == latest,
        s.aggregate.c.state.is_not(None), s.aggregate.c.municipality.is_not(None))
        .group_by(s.aggregate.c.state, s.aggregate.c.municipality)
        .order_by(s.aggregate.c.state, s.aggregate.c.municipality))]
    rows, cumulative, total = [], [], 0
    for state, city, quantity in weighted:
        if not quantity or quantity <= 0: continue
        total += quantity
        rows.append((state, city))
        cumulative.append(total)
    return {'rows': rows, 'cumulative': cumulative, 'total': total} if total else []
