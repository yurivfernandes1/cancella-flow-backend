from cadastros.models import Condominio, Unidade
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class UserCreateViewTests(APITestCase):
    def setUp(self):
        self.condominio = Condominio.objects.create(
            nome="Condominio Teste",
            cnpj="12345678000199",
            telefone="11999999999",
            cep="01001000",
            numero="100",
        )
        self.unidade = Unidade.objects.create(numero="101", bloco="A")

        self.admin = User.objects.create_user(
            username="admin",
            password="senha123",
            full_name="Admin User",
            email="admin@example.com",
            cpf="11144477735",
            phone="11988887777",
            is_staff=True,
            condominio=self.condominio,
        )

        self.sindico = User.objects.create_user(
            username="sindico",
            password="senha123",
            full_name="Sindico User",
            email="sindico@example.com",
            cpf="52998224725",
            phone="11977776666",
            condominio=self.condominio,
        )
        sindicos_group, _ = Group.objects.get_or_create(name="Síndicos")
        self.sindico.groups.add(sindicos_group)

    def test_nao_permite_morador_sem_unidade(self):
        self.client.force_authenticate(user=self.sindico)

        payload = {
            "user_type": "morador",
            "username": "morador_sem_unidade",
            "password": "senha123",
            "first_name": "Morador",
            "last_name": "SemUnidade",
            "email": "morador1@example.com",
            "cpf": "39053344705",
            "phone": "11999998888",
        }

        response = self.client.post(reverse("create"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Unidade", response.data.get("error", ""))

    def test_cria_sindico_morador_com_unidade_e_grupos(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            "user_type": "sindico_morador",
            "username": "sindico_morador_ok",
            "password": "senha123",
            "first_name": "Carlos",
            "last_name": "Silva",
            "email": "carlos.silva@example.com",
            "cpf": "12345678909",
            "phone": "11966665555",
            "condominio_id": self.condominio.id,
            "unidade_id": self.unidade.id,
        }

        response = self.client.post(reverse("create"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user_type"], "sindico_morador")

        created_user = User.objects.get(username="sindico_morador_ok")
        group_names = set(created_user.groups.values_list("name", flat=True))
        self.assertIn("Síndicos", group_names)
        self.assertIn("Moradores", group_names)
        self.assertEqual(created_user.unidade_id, self.unidade.id)

    def test_nao_permite_sindico_morador_sem_unidade(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            "user_type": "sindico_morador",
            "username": "sindico_sem_unidade",
            "password": "senha123",
            "first_name": "Ana",
            "last_name": "Oliveira",
            "email": "ana.oliveira@example.com",
            "cpf": "98765432100",
            "phone": "11955554444",
            "condominio_id": self.condominio.id,
        }

        response = self.client.post(reverse("create"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Unidade", response.data.get("error", ""))
