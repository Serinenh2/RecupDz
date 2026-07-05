from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Pagination par défaut de l'API — honore ?page_size=, déjà utilisé
    partout côté frontend mais jusqu'ici ignoré par PageNumberPagination."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 2000
