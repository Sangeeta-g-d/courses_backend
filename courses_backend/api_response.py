from rest_framework.response import Response
from rest_framework import status as drf_status


class APIResponseMixin:

    def success_response(
        self,
        message="Success",
        data=None,
        status_code=drf_status.HTTP_200_OK
    ):
        return Response(
            {
                "status": True,
                "message": message,
                "response": data if data is not None else []
            },
            status=status_code
        )

    def error_response(
        self,
        errors,
        status_code=drf_status.HTTP_400_BAD_REQUEST
    ):
        """
        errors can be:
        - serializer.errors (dict)
        - string
        """

        message = self._extract_error_message(errors)

        return Response(
            {
                "status": False,
                "message": message,
                "response": []
            },
            status=status_code
        )

    def _extract_error_message(self, errors):
        """
        Convert serializer.errors into a readable string
        """

        # If already a string
        if isinstance(errors, str):
            return errors

        # If DRF serializer errors (dict)
        if isinstance(errors, dict):
            messages = []

            for field, error_list in errors.items():
                if isinstance(error_list, list):
                    messages.append(f"{field}: {error_list[0]}")
                else:
                    messages.append(f"{field}: {error_list}")

            return " | ".join(messages)

        return "Something went wrong"
