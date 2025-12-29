# 🏢 Cancella Flow

<div align="center">
  <img src="./frontend/assets/logo_header.svg" alt="Cancella Flow Logo" width="200" style="margin-bottom: 20px"/>
</div>

<div align="center">

![Status do Projeto](https://img.shields.io/badge/status-Em%20Desenvolvimento-yellow?style=for-the-badge)
![Licença](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)
![Versão](https://img.shields.io/badge/version-1.0.0-2abb98?style=for-the-badge)

</div>

---

## 📋 Sobre o Projeto

**Cancella Flow** é uma plataforma completa e intuitiva para gestão de condomínios, desenvolvida para síndicos, administradoras e gestores de propriedades. O sistema centraliza todas as operações do dia a dia, desde o controle de portaria até a gestão financeira, proporcionando eficiência, segurança e transparência na administração condominial.

---

## ✨ Principais Funcionalidades

### 🏢 Gestão de Condomínios
- **Multi-Condomínios**: Administre diversos condomínios em uma única plataforma
- **Perfis e Permissões**: Sistema de permissões customizável para cada tipo de usuário (Admin, Síndico, Portaria, Moradores)
- **Dashboard Inteligente**: Visão geral com métricas e indicadores relevantes para cada perfil

### � Controle de Acesso
- **Portaria Inteligente**: Registro de entrada e saída de visitantes em tempo real
- **Gestão de Visitantes**: Cadastro, autorização e histórico completo de visitas
- **Controle por QR Code**: Sistema de identificação digital (em desenvolvimento)

### 📦 Gestão de Encomendas
- **Registro Automático**: Cadastro rápido de encomendas com código de rastreio
- **Notificações**: Avisos automáticos para moradores sobre chegada de encomendas
- **Histórico Completo**: Controle de retiradas e responsáveis

### 👥 Gestão de Pessoas
- **Cadastro de Moradores**: Informações completas de cada unidade
- **Gestão de Funcionários**: Controle de equipe da portaria e prestadores de serviço
- **Síndicos e Gestores**: Perfis administrativos com diferentes níveis de acesso

### 📢 Comunicação
- **Avisos e Comunicados**: Sistema de avisos direcionados por condomínio ou unidades específicas
- **Notificações em Tempo Real**: Alertas importantes para moradores e administradores

### � Recursos Adicionais (Em Desenvolvimento)
- � **Gestão de Boletos**: Controle financeiro e envio automatizado
- 🎉 **Reserva de Salão de Festas**: Agendamento online de áreas comuns
- � **Relatórios Gerenciais**: Análises e métricas para tomada de decisão
- � **Aplicativo Mobile**: Versão PWA para acesso via smartphone

---

## 🛠️ Stack Tecnológica

### Backend
<div align="center">

[![Python](https://img.shields.io/badge/-Python%203.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/-Django-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/-Django%20REST%20Framework-ff1709?style=for-the-badge&logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![JWT](https://img.shields.io/badge/-JWT%20Auth-000000?style=for-the-badge&logo=json-web-tokens&logoColor=white)](https://jwt.io/)
[![SQLite](https://img.shields.io/badge/-SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)

</div>

**Principais recursos do backend:**
- API RESTful completa com Django REST Framework
- Autenticação e autorização via Token JWT
- Sistema de permissões por grupos (Admin, Síndico, Portaria, Moradores)
- Middleware personalizado para controle de acesso
- Validações customizadas e serializers otimizados

### Frontend
<div align="center">

[![React](https://img.shields.io/badge/-React%2018-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/-Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![React Router](https://img.shields.io/badge/-React%20Router%20v6-CA4245?style=for-the-badge&logo=react-router&logoColor=white)](https://reactrouter.com/)
[![React Icons](https://img.shields.io/badge/-React%20Icons-E91E63?style=for-the-badge&logo=react&logoColor=white)](https://react-icons.github.io/react-icons/)
[![React Select](https://img.shields.io/badge/-React%20Select-FF6B6B?style=for-the-badge&logo=react&logoColor=white)](https://react-select.com/)

</div>

**Principais recursos do frontend:**
- Single Page Application (SPA) com React
- Build otimizado com Vite para desenvolvimento rápido
- Roteamento protegido por autenticação
- Context API para gerenciamento de estado global
- Componentes reutilizáveis e modulares
- Design responsivo e moderno
- PWA ready (Progressive Web App)

### DevOps & Infraestrutura
<div align="center">

[![Docker](https://img.shields.io/badge/-Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Docker Compose](https://img.shields.io/badge/-Docker%20Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docs.docker.com/compose/)

</div>

**Estrutura do projeto:**
```
base_sistema_django/
├── backend/               # Django REST API
│   ├── access/           # Autenticação e usuários
│   ├── cadastros/        # Encomendas, visitantes
│   └── app/              # Configurações do Django
├── frontend/             # React Application
│   ├── components/       # Componentes reutilizáveis
│   ├── pages/           # Páginas da aplicação
│   ├── context/         # Context API
│   └── services/        # API services
└── docker-compose.yml   # Orquestração de containers
```

---

## 🎯 Diferenciais

- ✅ **Interface Intuitiva**: Design moderno e fácil de usar
- ✅ **Multi-tenant**: Suporte para múltiplos condomínios
- ✅ **Controle Granular**: Permissões específicas por grupo de usuários
- ✅ **Tempo Real**: Atualizações e notificações instantâneas
- ✅ **Segurança**: Autenticação robusta e proteção de dados
- ✅ **Escalável**: Arquitetura preparada para crescimento
- ✅ **Open Source**: Código aberto sob licença MIT

---

## 👨‍💻 Autor

**Yuri Fernandes**

[![LinkedIn](https://img.shields.io/badge/-LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/yurivfernandes)
[![GitHub](https://img.shields.io/badge/-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/yurivfernandes)

---

## 📝 Licença

Este projeto está sob a licença MIT. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.

---

<div align="center">
  <p>Desenvolvido com 💚 por <a href="https://github.com/yurivfernandes">Yuri Fernandes</a></p>
  <p>⭐ Deixe uma estrela se este projeto foi útil!</p>
</div>