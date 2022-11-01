NIU Scooter Data to InfluxDB v1.x
=================================

Fetch Niu scooter data and push it to an influx database.


Dependencies
------------

```
git clone https://github.com/bradjc/niu-api
python3 setup.py install
```


Configuration
-------------

Create `/etc/niu-api/config.yaml`:

```
---
niuapi:
  email: <email>
  password: <password>
```

and `/etc/swarm-gateway/influx.conf`:

```
url=
port=443
username=
password=
database=
```
