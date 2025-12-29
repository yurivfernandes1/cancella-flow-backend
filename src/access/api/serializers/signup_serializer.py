from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class SignupSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(required=True)
    cpf = serializers.CharField(required=True, max_length=14)
    phone = serializers.CharField(required=True, max_length=15)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "full_name", "cpf", "phone", "email")

    def validate_cpf(self, value):
        if User.objects.filter(cpf=value).exists():
            raise serializers.ValidationError("Este CPF já está em uso.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("Este email já está em uso.")
        return value.lower()
