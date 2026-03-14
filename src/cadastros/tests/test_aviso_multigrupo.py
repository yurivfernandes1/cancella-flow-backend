from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from cadastros.models import Aviso, Condominio

User = get_user_model()


class AvisoMultigrupoTests(APITestCase):
    def setUp(self):
        self.condominio = Condominio.objects.create(
            nome="Condominio Avisos",
            cnpj="123123123000199",
            telefone="11999990000",
            cep="01310000",
            numero="12",
        )

        self.group_moradores, _ = Group.objects.get_or_create(name="Moradores")
        self.group_portaria, _ = Group.objects.get_or_create(name="Portaria")
        self.group_sindicos, _ = Group.objects.get_or_create(name="Síndicos")

        self.sindico = User.objects.create_user(
            username="sindico_avisos",
            password="senha123",
            full_name="Sindico Avisos",
            email="sindico.avisos@example.com",
            cpf="39053344705",
            phone="11911112222",
            condominio=self.condominio,
        )
        self.sindico.groups.add(self.group_sindicos)

        self.morador = User.objects.create_user(
            username="morador_avisos",
            password="senha123",
            full_name="Morador Avisos",
            email="morador.avisos@example.com",
            cpf="28625587887",
            phone="11933334444",
            condominio=self.condominio,
        )
        self.morador.groups.add(self.group_moradores)

    def test_cria_aviso_enviar_para_todos(self):
        self.client.force_authenticate(user=self.sindico)

        payload = {
            "titulo": "Aviso geral",
            "descricao": "Comunicado para todos os perfis.",
            "enviar_para_todos": True,
            "prioridade": "media",
            "status": "ativo",
            "data_inicio": timezone.now().isoformat(),
        }

        response = self.client.post(
            reverse("aviso-create"), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        aviso = Aviso.objects.get(id=response.data["id"])
        grupos = set(aviso.grupos.values_list("name", flat=True))
        self.assertEqual(grupos, {"Moradores", "Portaria", "Síndicos"})

    def test_morador_recebe_aviso_multigrupo(self):
        aviso = Aviso.objects.create(
            titulo="Aviso para moradores e portaria",
            descricao="Teste",
            grupo=self.group_moradores,
            prioridade="media",
            status="ativo",
            data_inicio=timezone.now(),
            created_by=self.sindico,
        )
        aviso.grupos.set([self.group_moradores, self.group_portaria])

        self.client.force_authenticate(user=self.morador)
        response = self.client.get(reverse("aviso-list"), {"vigente": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["results"])
        self.assertIn(
            aviso.id, [item["id"] for item in response.data["results"]]
        )

    def test_listagem_retorna_campos_grupos(self):
        aviso = Aviso.objects.create(
            titulo="Aviso estruturado",
            descricao="Teste campos",
            grupo=self.group_moradores,
            prioridade="alta",
            status="ativo",
            data_inicio=timezone.now(),
            created_by=self.sindico,
        )
        aviso.grupos.set([self.group_moradores, self.group_portaria])

        self.client.force_authenticate(user=self.morador)
        response = self.client.get(reverse("aviso-list"), {"vigente": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data["results"][0]
        self.assertIn("grupos", item)
        self.assertIn("grupos_nomes", item)
        self.assertTrue(len(item["grupos"]) >= 1)
