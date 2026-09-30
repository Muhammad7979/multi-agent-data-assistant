"""Trusted tool outcomes; independent of model-generated completion claims."""


def saved_result(stored, operation):
    return {
        'operation': operation, 'status': 'saved',
        'file': dict(id=stored.id, filename=stored.path.name, format=stored.format,
                     created_at=stored.created_at, size_bytes=stored.size_bytes,
                     row_count=stored.row_count),
    }


def failed_result(operation, code):
    return {'operation': operation, 'status': 'failed', 'error_code': code}
