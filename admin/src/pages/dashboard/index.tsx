import { useEffect, useState } from "react";
import { Card, Col, Row, Statistic } from "antd";

const API = import.meta.env.VITE_API_URL || "http://192.168.1.4:8100/api/v1";

export function Dashboard() {
  const [stats, setStats] = useState<Record<string, number>>({});

  useEffect(() => {
    fetch(`${API}/stats`)
      .then((r) => r.json())
      .then(setStats)
      .catch(console.error);
  }, []);

  const items = [
    ["Clientes", stats.clients],
    ["Inventario", stats.inventory_items],
    ["Catálogo", stats.catalog_products],
    ["Proveedores", stats.suppliers],
    ["Cotizaciones", stats.quotes],
    ["Visitas", stats.sop_visits],
  ];

  return (
    <div style={{ padding: 24 }}>
      <h1>PC Doctor OS — Panel</h1>
      <p>Servidor: 192.168.1.4 — MongoDB pcdoctor_swarm</p>
      <Row gutter={[16, 16]}>
        {items.map(([label, value]) => (
          <Col key={label as string} xs={24} sm={12} md={8} lg={4}>
            <Card>
              <Statistic title={label as string} value={value ?? 0} />
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
