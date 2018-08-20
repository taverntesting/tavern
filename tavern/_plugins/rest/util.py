try:
    from urllib.parse import urlparse, parse_qs
except ImportError:
    from urlparse import urlparse, parse_qs


def get_redirect_query_params(response):
    """If there was a redirect header, get any query parameters from it
    """

    try:
        redirect_url = response.headers["location"]
    except KeyError:
        redirect_query_params = {}
    else:
        parsed = urlparse(redirect_url)
        qp = parsed.query
        redirect_query_params = {i:j[0] for i, j in parse_qs(qp).items()}

    return redirect_query_params


def get_requests_response_information(response):
    """Get response parameters to print/log

    Args:
        response (requests.Response): response object from requests

    Returns:
        dict: dict containing body, headers, and redirect params
    """
    info = {}
    info["headers"] = response.headers

    try:
        info["body"] = response.json()
    except ValueError:
        info["body"] = None

    redirect_query_params = get_redirect_query_params(response)
    if redirect_query_params:
        parsed_url = urlparse(response.headers["location"])
        to_path = "{0}://{1}{2}".format(*parsed_url)
        info["redirect_query_params"] = redirect_query_params
        info["redirect_location"] = to_path
    else:
        info["redirect_query_params"] = None
        info["redirect_location"] = None

    return info
