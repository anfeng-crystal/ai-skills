"""One HTTP request at a time; a redirect does not extend the approved target."""

import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        # Stop before urllib parses Location, including unsupported URL schemes.
        raise urllib.error.HTTPError(req.full_url, code, "Redirect blocked", headers, fp)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def open_once(request, timeout):
    # Keep urllib's default verified HTTPS handling and avoid a global opener.
    return urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout)
