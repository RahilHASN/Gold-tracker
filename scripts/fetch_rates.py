"""Reads Bullions.co.in (unofficial rate site) and writes rates.json for the Gold Tracker page.
National rates every run; city pages about once an hour. Standard library only."""
import datetime as dt, html as H, json, os, re, sys, time, urllib.request

BASE = "https://bullions.co.in/"
UA = "GoldTrackerPersonal/1.0 (small personal rate checker; polite polling)"
CITIES = {"Mumbai": "mumbai", "Delhi": "delhi", "Chennai": "chennai", "Kolkata": "kolkata",
          "Bengaluru": "bangalore", "Hyderabad": "hyderabad", "Ahmedabad": "ahmedabad",
          "Pune": "pune", "Surat": "surat", "Jaipur": "jaipur", "Thiruvananthapuram": "thiruvananthapuram"}
NUM = r"(?:\|\s*)+([\d,]+(?:\.\d+)?)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def to_text(page):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page)
    t = re.sub(r"(?s)<[^>]+>", " | ", t)
    return re.sub(r"\s+", " ", H.unescape(t))


def num(t, label):
    m = re.search(label + r"[^|]*" + NUM, t)
    return float(m.group(1).replace(",", "")) if m else None


def parse(page):
    t = to_text(page)
    d = {"24": num(t, r"Gold\s*24\s*Karat"), "22": num(t, r"Gold\s*22\s*Karat"), "18": num(t, r"Gold\s*18\s*Karat")}
    mcx, cx = num(t, r"Gold\s*-\s*India\s*MCX"), num(t, r"Gold\s*-\s*US\s*Comex")
    if mcx: d["mcx10"] = mcx
    if cx: d["comex"] = cx
    m = re.search(r"Last\s*Update[\s|:]*([A-Za-z]+,\s*\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+\d{1,2}:\d{2}\s*[AP]M)", t)
    d["updatedText"] = (m.group(1) + " IST") if m else None
    return d


def check(d, ref=None, tol=0.15):
    if not d.get("24") or not d.get("22"):
        raise ValueError("24K or 22K rate not found")
    if not (3000 < d["24"] < 100000):
        raise ValueError("24K rate outside sane range: %s" % d["24"])
    if not (0.90 < d["22"] / d["24"] < 0.935):
        raise ValueError("22K/24K ratio looks wrong")
    if ref and ref.get("24") and abs(d["24"] / ref["24"] - 1) > tol:
        raise ValueError("24K moved more than %d%% versus reference" % (tol * 100))


def main():
    old = json.load(open("rates.json")) if os.path.exists("rates.json") else {}
    now = dt.datetime.now(dt.timezone.utc)
    nat = parse(get(BASE))
    print("national:", nat)
    check(nat, old.get("national"), 0.15)
    data = {"source": "Bullions.co.in (unofficial)", "fetchedAt": now.isoformat(timespec="seconds"),
            "national": nat, "cities": dict(old.get("cities", {}))}
    if now.minute < 15:
        for name, slug in CITIES.items():
            try:
                time.sleep(2)
                c = parse(get(BASE + "location/" + slug + "/"))
                check(c, nat, 0.08)
                data["cities"][name] = c
                print("city ok:", name, c["24"], c["22"])
            except Exception as e:
                print("city skipped:", name, "-", e)
    if old and old.get("national") == nat and old.get("cities") == data["cities"]:
        age = (now - dt.datetime.fromisoformat(old["fetchedAt"])).total_seconds()
        if age < 3 * 3600:
            print("unchanged; not writing")
            return
    json.dump(data, open("rates.json", "w"), indent=1, ensure_ascii=False)
    print("rates.json written")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAILED:", e)
        sys.exit(1)
