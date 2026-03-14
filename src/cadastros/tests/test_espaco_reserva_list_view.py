from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from cadastros.models import Condominio, Espaco, EspacoReserva, Unidade

User = get_user_model()


class EspacoReservaListViewTests(APITestCase):
    def setUp(self):
        self.condominio = Condominio.objects.create(
            nome="Condominio Reserva",
            cnpj="98765432000188",
            telefone="11911112222",
            cep="01310000",
            numero="200",
        )
        self.unidade = Unidade.objects.create(numero="202", bloco="B")

        self.sindico = User.objects.create_user(
            username="sindico_reserva",
            password="senha123",
            full_name="Sindico Reserva",
            email="sindico.reserva@example.com",
            cpf="15350946056",
            phone="11922223333",
            condominio=self.condominio,
        )
        group_sindico, _ = Group.objects.get_or_create(name="Síndicos")
        self.sindico.groups.add(group_sindico)

        self.morador = User.objects.create_user(
            username="morador_reserva",
            password="senha123",
            full_name="Morador Reserva",
            email="morador.reserva@example.com",
            cpf="28625587887",
            phone="11933334444",
            condominio=self.condominio,
            unidade=self.unidade,
        )
        group_morador, _ = Group.objects.get_or_create(name="Moradores")
        self.morador.groups.add(group_morador)

        self.espaco = Espaco.objects.create(
            nome="Salao de Festas",
            capacidade_pessoas=50,
            valor_aluguel="350.00",
            created_by=self.sindico,
        )

        self.reserva = EspacoReserva.objects.create(
            espaco=self.espaco,
            morador=self.morador,
            data_reserva=date.today() + timedelta(days=1),
            valor_cobrado="350.00",
            status="confirmada",
            created_by=self.morador,
        )

    def test_lista_reservas_retorna_created_on(self):
        self.client.force_authenticate(user=self.morador)

        response = self.client.get(reverse("espaco-reserva-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["results"])
        first_item = response.data["results"][0]
        self.assertIn("created_on", first_item)
        self.assertIsNotNone(first_item["created_on"])
