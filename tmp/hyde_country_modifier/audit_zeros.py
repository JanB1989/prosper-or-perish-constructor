import pandas as pd

p = "tmp/hyde1300/cropland_per_person.csv"
d = pd.read_csv(p)
v = "Land use (per capita): Cropland"

def interp(year, a, b):
    x = d[d.Year.isin([a,b])].pivot(index=["Entity","Code"], columns="Year", values=v)
    f = (year-a)/(b-a)
    return (x[a] + f*(x[b]-x[a])).rename("value").reset_index()

for year,a,b in [(1337,1300,1400),(1837,1830,1840)]:
    x=interp(year,a,b)
    exact=x[x.value.eq(0)]
    rounded=x[(x.value.gt(0)) & (x.value.lt(.005))]
    print("YEAR",year,"rows",len(x),"exact_zero",len(exact),"positive_rounds_to_0.00",len(rounded))
    print("EXACT", exact.Entity.tolist())
    print("ROUNDS", rounded[["Entity","value"]].to_dict("records"))

area=pd.read_csv("tmp/hyde1300/cropland_area.csv")
print(area[(area.Entity.isin(["Canada","Australia","Cuba","Haiti","Somalia","Uruguay"])) & area.Year.isin([1300,1400,1830,1840])].to_string(index=False))
