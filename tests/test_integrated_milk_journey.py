"""One authenticated API journey across production, transport and reception."""
import uuid

import pytest

from apps.accounts.models import User
from apps.catalog.models import Location, Presentation
from apps.notifications.models import Notification
from apps.traceability.models import Conformity, Lot, Transfer
from tests.test_access import assign
from tests.test_milking_confirm import complete_command, confirm_command
from tests.test_transfer_pickup import physical_command
from tests.test_transfer_reads import client_for
from tests.test_transfer_send import send_command

pytestmark = pytest.mark.django_db


def test_vilma_lolo_maria_same_document(user):
    producer = client_for(user)
    milking_command = complete_command(user)
    created_milking = producer.post('/api/v1/milkings', milking_command, format='json')
    assert created_milking.status_code == 200, created_milking.data
    confirmed_milking = producer.post(
        f"/api/v1/milkings/{milking_command['entity_id']}/confirm",
        confirm_command(milking_command), format='json',
    )
    assert confirmed_milking.status_code == 200, confirmed_milking.data
    assert confirmed_milking.json()['result']['quantity'] == '5.500'
    lot = Lot.objects.get()
    destination = Location.objects.create(code='INTEGRACION_PV', name='Punto de venta', kind='PUNTO_VENTA')
    driver = User.objects.create_user(username='lolo', name='Lolo')
    receiver = User.objects.create_user(username='maria', name='María')
    assign(driver, 'TRANSPORTE', lot.production.center)
    assign(receiver, 'RECEPCION', destination)
    presentation = Presentation.objects.create(product=lot.production.product, name='Bolsa 1 L', content_base='1.000')
    draft = {
        'event_id': str(uuid.uuid4()), 'device_id': milking_command['device_id'],
        'entity_id': str(uuid.uuid4()), 'occurred_at': milking_command['occurred_at'],
        'depends_on': [], 'payload': {
            'version_id': str(uuid.uuid4()), 'line_id': str(uuid.uuid4()),
            'lot_id': str(lot.id), 'presentation_id': str(presentation.id),
            'units': '5.000', 'destination_id': str(destination.id),
            'driver_id': str(driver.id), 'receiver_id': str(receiver.id),
        },
    }
    created = producer.post('/api/v1/transfers', draft, format='json')
    assert created.status_code == 200, created.data
    sent = producer.post(f"/api/v1/transfers/{draft['entity_id']}/send", send_command(draft), format='json')
    assert sent.status_code == 200, sent.data
    transfer = sent.json()['result']
    assert transfer['state'] == 'PENDIENTE_RECOGIDA'
    assert transfer['current_version']['lines'][0]['quantity'] == '5.000'
    assert transfer['current_version']['driver_id'] == str(driver.id)
    assert transfer['current_version']['receiver_id'] == str(receiver.id)
    assert Notification.objects.filter(recipient=driver, type='PICKUP_REQUESTED').count() == 1
    record = Transfer.objects.get(pk=draft['entity_id'])
    pickup = physical_command(record, driver)
    received_by_driver = client_for(driver).post(f'/api/v1/transfers/{record.id}/pickup', pickup, format='json')
    assert received_by_driver.status_code == 200, received_by_driver.data
    assert received_by_driver.json()['result']['state'] == 'EN_CAMINO'
    assert Notification.objects.filter(recipient=receiver, type='RECEPTION_PENDING').count() == 1
    record.refresh_from_db()
    reception = physical_command(record, receiver, 'TRANSFER_RECEIVE')
    accepted = client_for(receiver).post(f'/api/v1/transfers/{record.id}/receive', reception, format='json')
    assert accepted.status_code == 200, accepted.data
    assert accepted.json()['result']['state'] == 'RECIBIDO'
    assert Conformity.objects.filter(version__transfer=record, stage='RECOGIDA').count() == 1
    assert Conformity.objects.filter(version__transfer=record, stage='RECEPCION').count() == 1
    assert Notification.objects.filter(recipient=user, type='RECEPTION_CONFIRMED').count() == 1
    for actor in (user, driver, receiver):
        detail = client_for(actor).get(f'/api/v1/transfers/{record.id}')
        assert detail.status_code == 200
        assert detail.json()['state'] == 'RECIBIDO'
