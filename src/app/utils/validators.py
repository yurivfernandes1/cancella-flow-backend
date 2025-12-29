import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_cpf(value):
    """
    Valida se o CPF está em formato válido e se os dígitos verificadores estão corretos.
    """
    # Remove caracteres não numéricos
    cpf = re.sub(r"\D", "", str(value))

    # Verifica se tem 11 dígitos
    if len(cpf) != 11:
        raise ValidationError(_("CPF deve conter exatamente 11 dígitos."))

    # Verifica se todos os dígitos são iguais
    if cpf == cpf[0] * 11:
        raise ValidationError(_("CPF inválido."))

    # Calcula o primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto

    # Verifica o primeiro dígito
    if int(cpf[9]) != digito1:
        raise ValidationError(_("CPF inválido."))

    # Calcula o segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto

    # Verifica o segundo dígito
    if int(cpf[10]) != digito2:
        raise ValidationError(_("CPF inválido."))


def validate_phone(value):
    """
    Valida se o telefone está em formato válido (formato brasileiro).
    Aceita formatos: (XX) XXXXX-XXXX, (XX) XXXX-XXXX, XX XXXXX-XXXX, XX XXXX-XXXX
    Ou apenas números: XXXXXXXXXXX ou XXXXXXXXXX
    """
    # Remove caracteres não numéricos
    phone = re.sub(r"\D", "", str(value))

    # Verifica se tem 10 ou 11 dígitos (com ou sem 9 no celular)
    if len(phone) not in [10, 11]:
        raise ValidationError(_("Telefone deve conter 10 ou 11 dígitos."))

    # Se tem 11 dígitos, o terceiro deve ser 9 (celular)
    if len(phone) == 11 and phone[2] != "9":
        raise ValidationError(
            _("Para telefones com 11 dígitos, o terceiro dígito deve ser 9.")
        )

    # Verifica se os dois primeiros dígitos formam um DDD válido (11 a 99)
    ddd = phone[:2]
    if not (11 <= int(ddd) <= 99):
        raise ValidationError(_("DDD inválido. Deve estar entre 11 e 99."))


def format_cpf(value):
    """
    Formata o CPF no padrão XXX.XXX.XXX-XX
    """
    cpf = re.sub(r"\D", "", str(value))
    if len(cpf) == 11:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    return value


def format_phone(value):
    """
    Formata o telefone no padrão (XX) XXXXX-XXXX ou (XX) XXXX-XXXX
    """
    phone = re.sub(r"\D", "", str(value))
    if len(phone) == 11:
        return f"({phone[:2]}) {phone[2:7]}-{phone[7:]}"
    elif len(phone) == 10:
        return f"({phone[:2]}) {phone[2:6]}-{phone[6:]}"
    return value
