from decimal import Decimal
import html.parser
import re
import requests

class PaketomatException(Exception):
    pass

class LoginFailedException(PaketomatException):
    pass

class RecipientAlreadyExistsException(PaketomatException):
    pass

class NoRouteException(PaketomatException):
    pass

class Sender:

    def __init__(self, *args, **kwargs):
        for k in ["sender_id", "name", "address", "customer_id", "depot"]:
            self.__dict__[k] = kwargs.get(k)

    def __str__(self):
        return self.name

class Recipient:

    def __init__(self, *args, **kwargs):
        for k in ["customer_id", "name", "additional", "contact_person", "phonenumber", "street", "postal_code", "city", "country_code", "email"]:
            self.__dict__[k] = kwargs.get(k)

class Route:

    def __init__(self, *args, **kwargs):
        for k in ["ausgDepot", "osort", "dsort", "ddepot", "service", "service_text", "country_code", "numeric_country_code", "plz", "usedversion", "iata", "groupingpriority", "router", "code"]:
            self.__dict__[k] = kwargs.get(k)

        if not self.router:
            self.router = "%s-%s-%s" % (self.service, self.country_code, self.plz)

        if not self.code:
            self.code = "%s-%s" % (self.country_code, self.ddepot)
            if self.iata:
                self.code += "-%s" % self.iata
                if self.groupingpriority:
                    self.code += "-%s" % self.groupingpriority

class PaketomatBrowser:

    PRINTER_NAME = "Gutenberg Printing Press"

    def __init__(self):
        self._sess = requests.Session()
        req = self._sess.get("http://web.paketomat.at/")

    def _encode_body(self, body):
        return [(str(x[0]).encode("iso8859-1"), str(x[1]).encode("iso8859-1")) for x in body.items()]

    def login(self, username, password):
        body = {
            "doLogin": "true",
            "compName": "PaketomatBrowser-PC",
            "clientIP": "127.0.0.1",
            "clientUsername": "PaketomatBrowser",
            "printerlist": self.PRINTER_NAME + ";",
            "username": username,
            "passwort": password, # Note the t
            "anmelden": "Anmelden",
        }
        req = self._sess.post("http://web.paketomat.at/", data=self._encode_body(body))
        match = re.search(r"<div class=\"userInfo\">\s+([0-9]+)\s-", req.text)
        if not (match and match.group(1) == username):
            raise LoginFailedException()

        body = {
            "druckertyp": "labeldrucker",
            "etiketten_drucker": self.PRINTER_NAME,
            "listen_drucker": self.PRINTER_NAME,
            "etiketten_groesse": "163x105",
            "vierProBlatt": "false",
            "linker_rand": 0,
            "obrerer_rand": 0,
            "horizontale_ausrichtung": "links",
            "vertikale_ausrichtung": "oben",
            "papier_ausrichtung": "hoch"
        }
        req = self._sess.post("http://web.paketomat.at/settings/ajax/savePrintConfiguration.php", data=self._encode_body(body))

    def create_recipient(self, recipient):
        if not recipient.customer_id:
            req = self._sess.get("http://web.paketomat.at/kundenstamm/new.php")
            match = re.search(r"<input name=\"knr\"\s+.*?\s+value=([0-9]+)>", req.text)
            if not match:
                raise PaketomatException("Could not find next customer id")
            recipient.customer_id = int(match.group(1))

        body = {
            "knr": recipient.customer_id,
            "mandant": "",
            "name": recipient.name,
            "plz": recipient.postal_code,
            "zusatz": recipient.additional or "",
            "ort": recipient.city,
            "bezperson": recipient.contact_person or "",
            "tel": recipient.phonenumber or "",
            "land": recipient.country_code.upper(),
            "strasse": recipient.street,
            "email": recipient.email or ""
        }
        req = self._sess.post("http://web.paketomat.at/kundenstamm/ajax/doSave.php", data=self._encode_body(body))
        match = re.search(r"<div align='center' class='(?:error|message)'>(.*?)</div>", req.text)
        if not match:
            raise PaketomatException("Unexpected response")
        if match.group(1) == "Fehler beim Speichern der Daten!<br>Kundennummer bereits vorhanden!":
            raise RecipientAlreadyExistsException()
        if match.group(1) != "Daten erfolgreich angelegt":
            raise PaketomatException("Unexpected response: %s" % match.group(1))

    def get_senders(self):
        req = self._sess.get("http://web.paketomat.at/labeldruck/index.php")
        match = re.search(r"<div id=\"mandantContainer\">\s+<fieldset>\s+(.*?)\s+</fieldset>\s+</div>", req.text, re.DOTALL)

        if not match:
            raise PaketomatException("Could not find 'mandantContainer'")
        mandanten_fieldset = match.group(1)

        mandanten = {}
        for match in re.finditer(r"<option value=\"([0-9]+)\">(.*?)</option>", mandanten_fieldset):
            if match.group(2) in mandanten:
                raise PaketomatException("Duplicate sender name")
            mandanten[match.group(2)] = int(match.group(1))

        req = self._sess.get("http://web.paketomat.at/settings/mandanten.php")
        text = req.text.replace("\r", "\n") # Fuuuuuu

        senders = []
        hp = html.parser.HTMLParser()

        for match in re.finditer(r"<tr class='(?:even|odd)'>\s+"
                                  "<td align=\"left\" style=\"\">[0-9]+</td>\s+"
                                  "<td align=\"left\" style=\"\">(.+?)</td>\s+"
                                  "<td align=\"left\" style=\"\">(.+?)</td>\s+"
                                  "<td align=\"left\" style=\"\">([0-9]+)</td>\s+"
                                  "<td align=\"left\" style=\"\">(.+?)</td>\s+</tr>", text):
            sender = Sender(
                sender_id=mandanten[match.group(1)],
                name=hp.unescape(match.group(1)),
                address=hp.unescape(match.group(2)),
                customer_id=int(match.group(3)),
                depot=hp.unescape(match.group(4))
            )
            senders.append(sender)

        return senders

    def get_parcel_tracking_number(self, reference_number):
        body = {
            "mandant": "",
            "knr": "",
            "pnr": "",
            "name": "",
            "lfnr": reference_number,
            "rnr": "",
            "strasse": "",
            "vdat": "01.01.1970",
            "dpd": "DPD",
            "plz": "",
            "land": "",
            "bdat": "18.01.2036",
            "pt": "Primetime",
            "ort": "",
            "vgew": "von",
            "bgew": "bis",
            "storniert": "storniert",
            "sortNach": "paknr",
            "sortWie": "asc",
        }
        req = self._sess.post("http://web.paketomat.at/archiv/ajax/doStornoSearch.php", data=self._encode_body(body))

        match = re.search(r"<table id=\"searchResultTable\" .*?>\s+<thead>.*?</thead>\s+<tbody>(.+?)</tbody>\s+</table>", req.text, re.DOTALL)
        if not match:
            raise PaketomatException("Unable to find search result table")
        results_table = match.group(1)

        match = re.search("<td>([0-9 ]+)</td>", results_table)
        if not match:
            raise PaketomatException("Unable to find tracking number")
        return match.group(1).replace(" ", "")

    def get_business_account(self):
        body = {
            "mandant": "",
            "knr": "",
            "pnr": "",
            "name": "",
            "lfnr": "",
            "rnr": "",
            "strasse": "",
            "vdat": "01.01.1970",
            "dpd": "DPD",
            "plz": "",
            "land": "",
            "bdat": "18.01.2036",
            "pt": "Primetime",
            "ort": "",
            "vgew": "von",
            "bgew": "bis",
            "storniert": "storniert",
            "sortNach": "paknr",
            "sortWie": "asc",
        }
        req = self._sess.post("http://web.paketomat.at/archiv/ajax/doStornoSearch.php", data=self._encode_body(body))

        match = re.search(r"<table id=\"searchResultTable\" .*?>\s+<thead>.*?</thead>\s+<tbody>(.+?)</tbody>\s+</table>", req.text, re.DOTALL)
        if not match:
            raise PaketomatException("Unable to find search result table")
        results_table = match.group(1)

        match = re.search(r"onclick=\"openBusiness\('[0-9]+', '[0-9]+' , '.+' , '([0-9]+)','(.+)'\);\"", results_table)
        if not match:
            raise PaketomatException("Unable to find DPD Business password")
        return match.groups()

    def find_route(self, sender_id, recipient, weight):
        body = {
            "r": recipient.customer_id,
            "p": "NP" if weight > 3 else "KP",
            "p2": "",
            "m": sender_id,
            "n": "false",
            "plz": "",
            "land": "",
            "p3": "",
            "p4": "",
            "p5": "",
            "p6": "",
            "p7": "null",
            "gewicht": weight,
            "versandart": "DPD", # FIXME
        }
        req = self._sess.post("http://web.paketomat.at/labeldruck/ajax/findRoute.php", data=self._encode_body(body))
        data = req.json()

        if data["ok"] != "ok":
            raise NoRouteException()

        return Route(
            ausgDepot=data["ausgDepot"],
            osort=data["osort"],
            dsort=data["dsort"],
            ddepot=data["ddepot"],
            service=data["service"],
            service_text=data["servicetext"],
            country_code=data["land"],
            numeric_country_code=data["countrycode"],
            plz=data["plz"],
            usedversion=data["usedversion"],
            iata=data.get("iata"),
            groupingpriority=data.get("groupingpriority"),
            router=data.get("router"),
            code=data.get("code"),
        )

    def create_parcel(self, date, sender_id, route, recipient, weight, reference_numbers=None, invoice_numbers=None):
        body = {
            "mandant": sender_id,
            "anzvon": 1,
            "anzbis": 1,
            "kg": weight,
            "selnr": "lfsnr",
            "nr": "",
            "lfnr": reference_numbers[0] if reference_numbers else "",
            "lfnummern": "~".join(reference_numbers) if reference_numbers else "",
            "rnrnummern": "~".join(invoice_numbers) if invoice_numbers else "",
            "ausgDepot": route.ausgDepot,
            "versanddat": date.strftime("%d.%m.%Y"),
            "versandart": "DPD", # FIXME
            "nummer": recipient.customer_id,
            "landort": "%s-%s-%s" % (recipient.country_code, recipient.postal_code, recipient.city.replace("-", "/")),
            "name": recipient.name,
            "zusatz": recipient.additional or "",
            "emailaviso": recipient.email or "",
            "bezperson": recipient.contact_person or "",
            "tel": recipient.phonenumber or "",
            "strasse": recipient.street,
            "paktyp1": "NP" if weight > 3 else "KP",
            "service": route.service_text,
            "osort": route.osort,
            "router": route.router,
            "dsort": route.dsort,
            "kennz": "",
            "code": route.code,
            "verrout": route.usedversion,
            "countrycode": route.numeric_country_code,
            "serviceinfo": "",
            "ok": "Routing OK!",
            "drucken": "Etikett drucken",
            "aube": "",
        }
        empty = ["paktyp2", "paktyp3", "paktyp4", "paktyp5", "paktyp6",
                 "lname", "lzusatz", "lemailaviso", "lbezperson", "ltel", "lstrasse", "lplz", "lort", "lland",
                 ]
        for k in empty:
            body[k] = ""

        req = self._sess.post("http://web.paketomat.at/labeldruck/pdf.php", data=self._encode_body(body))
        match = re.search(r"<param name=\"documenturl\" value=\"(http://web.paketomat.at/.*\.pdf)\"/>", req.text)
        if not match:
            raise PaketomatException("No PDF file found")

        req = self._sess.get(match.group(1))
        return req.content

    def get_parcel_weight(self, tracking_number):
        if not hasattr(self, "business_account"):
            self._business_account = self.get_business_account()

        params = {
            "pknr": tracking_number,
            "u": self._business_account[0],
            "p2": self._business_account[1],
        }
        req = requests.get("http://www.dpd-business.at/strack.php", params=params)
        match = re.search(r"<br>&nbsp;Gewicht:&nbsp; ([0-9]+(?:\.[0-9]+)?) kg", req.text)
        if not match:
            raise PaketomatException("No weight information found")
        return Decimal(match.group(1))

    def cancel_parcel(self, tracking_number):
        body = {
            "mandant": "",
            "knr": "",
            "pnr": tracking_number,
            "name": "",
            "lfnr": "",
            "rnr": "",
            "strasse": "",
            "vdat": "01.01.1970",
            "dpd": "DPD",
            "plz": "",
            "land": "",
            "bdat": "18.01.2036",
            "pt": "Primetime",
            "ort": "",
            "vgew": "von",
            "bgew": "bis",
            "storniert": "storniert",
            "sortNach": "paknr",
            "sortWie": "asc",
        }
        req = self._sess.post("http://web.paketomat.at/archiv/ajax/doStornoSearch.php", data=self._encode_body(body))

        match = re.search(r"<table id=\"searchResultTable\" .*?>\s+<thead>.*?</thead>\s+<tbody>(.+?)</tbody>\s+</table>", req.text, re.DOTALL)
        if not match:
            raise PaketomatException("Unable to find search result table")
        results_table = match.group(1)

        match = re.search(r"onclick=\"doStorno\(this, '([0-9]+)', '([0-9]+[0-9A-Z])'\);\"", results_table)
        if not match:
            raise PaketomatException("Unable to find storno link")

        body = {
            "id": match.group(1),
            "paknr": match.group(2),
        }
        req = self._sess.post("http://web.paketomat.at/archiv/ajax/doStorno.php", data=self._encode_body(body))

        if req.status_code != 200:
            raise PaketomatException("Unexpected status code %i" % req.status_code)
