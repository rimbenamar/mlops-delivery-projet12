import argparse
import random
import time
import httpx

p=argparse.ArgumentParser()
p.add_argument("--url",default="http://localhost:8000")
p.add_argument("--count",type=int,default=300)
p.add_argument("--drift",action="store_true")
a=p.parse_args()
with httpx.Client(timeout=20) as client:
    samples=client.get(a.url+"/dashboard/traffic-sample");samples.raise_for_status();d=samples.json()
    for i in range(a.count):
        row=list(random.choice(d["samples"]))
        if a.drift: row[0]=5000.;row[1]=50.;row[4]=3.
        body=dict(zip(d["features"],row))
        for field in ["promised_days","item_count","purchase_weekday","purchase_month"]:body[field]=int(body[field])
        r=client.post(a.url+"/predict",json=body);r.raise_for_status()
        if i%50==0:print(i,r.json())
        time.sleep(.1)
