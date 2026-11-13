"""Transform the six original Olist CSV tables. No raw identifiers are exported.
Usage: python scripts/prepare_data.py --raw /path/to/csv-or-csv.gz
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

FEATURES = ["distance_km", "weight_kg", "price_brl", "freight_brl", "promised_days", "item_count", "purchase_weekday", "purchase_month"]

def prepare(raw, output):
    sources = {}
    def read(name):
        path = raw / f"olist_{name}_dataset.csv.gz"
        if not path.exists(): path = raw / f"olist_{name}_dataset.csv"
        sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return pd.read_csv(path)
    orders, items, customers, sellers, products, geo = [read(n) for n in ["orders","order_items","customers","sellers","products","geolocation"]]
    geo = geo[geo.geolocation_lat.between(-34,6) & geo.geolocation_lng.between(-74,-34)]
    coords = geo.groupby("geolocation_zip_code_prefix")[["geolocation_lat","geolocation_lng"]].median()
    customers = customers.merge(coords,left_on="customer_zip_code_prefix",right_index=True,how="left").rename(columns={"geolocation_lat":"customer_lat","geolocation_lng":"customer_lng"})
    sellers = sellers.merge(coords,left_on="seller_zip_code_prefix",right_index=True,how="left").rename(columns={"geolocation_lat":"seller_lat","geolocation_lng":"seller_lng"})
    detail = items.merge(products[["product_id","product_weight_g"]],on="product_id",validate="many_to_one")
    detail = detail.merge(sellers[["seller_id","seller_lat","seller_lng"]],on="seller_id",validate="many_to_one")
    agg = detail.groupby("order_id").agg(sellers=("seller_id","nunique"), weight_g=("product_weight_g",lambda x: x.sum(min_count=len(x))), price_brl=("price","sum"),freight_brl=("freight_value","sum"),item_count=("order_item_id","size"),seller_lat=("seller_lat","first"),seller_lng=("seller_lng","first"))
    # A single seller gives an unambiguous seller-to-customer distance.
    agg = agg[agg.sellers.eq(1)]
    frame = orders[orders.order_status.eq("delivered")].merge(agg,on="order_id",validate="one_to_one")
    frame = frame.merge(customers[["customer_id","customer_lat","customer_lng"]],on="customer_id",validate="many_to_one")
    for c in ["order_purchase_timestamp","order_estimated_delivery_date","order_delivered_customer_date"]:
        frame[c] = pd.to_datetime(frame[c],errors="coerce")
    frame = frame.dropna(subset=["order_purchase_timestamp","order_estimated_delivery_date","order_delivered_customer_date","weight_g","seller_lat","seller_lng","customer_lat","customer_lng"])
    a,b,c,d=[np.radians(frame[k]) for k in ["seller_lat","seller_lng","customer_lat","customer_lng"]]
    h=np.sin((c-a)/2)**2+np.cos(a)*np.cos(c)*np.sin((d-b)/2)**2
    frame["distance_km"]=6371*2*np.arcsin(np.sqrt(np.clip(h,0,1)))
    frame["weight_kg"]=frame.weight_g/1000
    frame["promised_days"]=(frame.order_estimated_delivery_date.dt.normalize()-frame.order_purchase_timestamp.dt.normalize()).dt.days
    frame["purchase_weekday"]=frame.order_purchase_timestamp.dt.dayofweek
    frame["purchase_month"]=frame.order_purchase_timestamp.dt.month
    frame["late"]=(frame.order_delivered_customer_date.dt.normalize()>frame.order_estimated_delivery_date.dt.normalize()).astype(int)
    frame["purchase_date"]=frame.order_purchase_timestamp
    frame=frame[frame.weight_kg.between(.001,100) & frame.distance_km.between(0,6000) & frame.price_brl.between(.01,30000) & frame.freight_brl.between(0,5000) & frame.promised_days.between(1,100) & frame.item_count.between(1,50)]
    frame=frame.sort_values("purchase_date",kind="stable")[["purchase_date",*FEATURES,"late"]].reset_index(drop=True)
    for c in ["distance_km","weight_kg","price_brl","freight_brl"]:frame[c]=frame[c].round(4)
    output.mkdir(parents=True,exist_ok=True)
    target=output/"deliveries.csv"
    frame.to_csv(target,index=False)
    metadata={"name":"Brazilian E-Commerce Public Dataset by Olist", "source":"https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce", "mirror":"https://github.com/infobarbosa/dataset-olist", "license":"CC BY-NC-SA 4.0", "rows":len(frame), "late_rate":float(frame.late.mean()),"start":str(frame.purchase_date.min()),"end":str(frame.purchase_date.max()),"sha256":hashlib.sha256(target.read_bytes()).hexdigest(), "raw_sha256":sources, "transformation":"Delivered, single-seller orders; complete weights/geolocation; documented numeric bounds; calendar-day late label; no identifiers exported."}
    (output/"metadata.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    print(json.dumps(metadata,indent=2))

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--raw",type=Path,required=True);parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[1]/"data");args=parser.parse_args();prepare(args.raw,args.output)
