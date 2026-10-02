from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {key: ["Campo no permitido."] for key in sorted(unknown)}
                )
        return super().to_internal_value(data)
