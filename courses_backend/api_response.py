from rest_framework.response import Response
from rest_framework import status as drf_status
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.exceptions import APIException


class APIResponseMixin:

    def success_response(
        self,
        message="Success",
        data=None,
        status_code=drf_status.HTTP_200_OK
    ):
        return Response(
            {
                "status": status_code,
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

        message = _extract_error_message(errors)

        return Response(
            {
                "status": status_code,
                "message": message,
                "response": []
            },
            status=status_code
        )


def _extract_error_message(errors):
    """
    Convert error details into a readable string.
    Used by both APIResponseMixin and custom_exception_handler.
    
    errors can be:
    - string
    - dict (serializer.errors)
    - list
    """
    # If already a string
    if isinstance(errors, str):
        return errors
    
    # If list, join the items
    if isinstance(errors, list):
        if len(errors) > 0:
            # If list contains strings, join them
            if isinstance(errors[0], str):
                return " | ".join(errors)
            # If list contains dicts or other structures, process first item
            return _extract_error_message(errors[0])
        return "Something went wrong"
    
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


def custom_exception_handler(exc, context):
    """
    Custom exception handler that converts DRF exceptions to the standard API response format.
    
    Returns responses in the format:
    {
        "status": status_code,
        "message": error_message,
        "response": []
    }
    """
    # Call DRF's default exception handler first
    response = drf_exception_handler(exc, context)
    
    # If response is None, it means DRF doesn't know how to handle this exception
    # Fall back to DRF's default behavior (return None to let Django handle it)
    if response is None:
        return None
    
    # Check if it's a DRF APIException
    if isinstance(exc, APIException):
        # Extract error message from exception.detail
        error_detail = exc.detail
        message = _extract_error_message(error_detail)
        
        # Get status code from the exception
        status_code = exc.status_code
        
        # Return standard format response
        return Response(
            {
                "status": status_code,
                "message": message,
                "response": []
            },
            status=status_code
        )
    
    # For non-DRF exceptions, return the original DRF response
    return response
