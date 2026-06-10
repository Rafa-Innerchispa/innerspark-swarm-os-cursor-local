import { List, useTable } from "@refinedev/antd";
import { Table } from "antd";

export function ClientList() {
  const { tableProps } = useTable({ resource: "clients", syncWithLocation: true });

  return (
    <List title="Clientes (DB04)">
      <Table {...tableProps} rowKey="client_id" scroll={{ x: 1200 }}>
        <Table.Column dataIndex="name" title="Nombre" />
        <Table.Column dataIndex="ruc" title="RUC" />
        <Table.Column dataIndex="city" title="Ciudad" />
        <Table.Column dataIndex="email" title="Email" />
        <Table.Column dataIndex="estado" title="Estado" />
        <Table.Column dataIndex="hub_ready" title="Hub" render={(v) => (v ? "Sí" : "No")} />
      </Table>
    </List>
  );
}
