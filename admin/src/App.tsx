import { Refine, ResourceProps } from "@refinedev/core";
import { ThemedLayoutV2, RefineThemes, useNotificationProvider } from "@refinedev/antd";
import { ConfigProvider, App as AntApp } from "antd";
import routerBindings, { UnsavedChangesNotifier } from "@refinedev/react-router-v6";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";
import {
  TeamOutlined,
  ShoppingOutlined,
  AppstoreOutlined,
  ShopOutlined,
  FileTextOutlined,
  CarOutlined,
  DashboardOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { dataProvider } from "./providers/dataProvider";
import { ClientList } from "./pages/clients/list";
import { Dashboard } from "./pages/dashboard";
import { GenericList } from "./pages/generic/List";
import { SettingsPage } from "./pages/settings";

const resources: ResourceProps[] = [
  { name: "clients", list: "/clients", meta: { label: "Clientes", icon: <TeamOutlined /> } },
  { name: "inventory-items", list: "/inventory", meta: { label: "Inventario", icon: <ShoppingOutlined /> } },
  { name: "catalog-products", list: "/catalog", meta: { label: "Catálogo", icon: <AppstoreOutlined /> } },
  { name: "suppliers", list: "/suppliers", meta: { label: "Proveedores", icon: <ShopOutlined /> } },
  { name: "quotes", list: "/quotes", meta: { label: "Cotizaciones", icon: <FileTextOutlined /> } },
  { name: "sop-visits", list: "/visits", meta: { label: "Visitas SOP", icon: <CarOutlined /> } },
  { name: "settings", list: "/settings", meta: { label: "Configuración", icon: <SettingOutlined /> } },
];

export default function App() {
  return (
    <BrowserRouter>
      <ConfigProvider
        theme={{
          ...RefineThemes.Blue,
          token: { colorPrimary: "#1e3a8a", colorError: "#dc2626" },
        }}
      >
        <AntApp>
          <Refine
            dataProvider={dataProvider}
            routerProvider={routerBindings}
            notificationProvider={useNotificationProvider}
            resources={resources}
            options={{ syncWithLocation: true, warnWhenUnsavedChanges: true }}
          >
            <Routes>
              <Route
                element={
                  <ThemedLayoutV2 Title={() => <span>PC Doctor OS</span>}>
                    <Outlet />
                  </ThemedLayoutV2>
                }
              >
                <Route index element={<Dashboard />} />
                <Route path="/clients" element={<ClientList />} />
                <Route path="/inventory" element={<GenericList resource="inventory-items" title="Inventario hardware (DB26)" />} />
                <Route path="/catalog" element={<GenericList resource="catalog-products" title="Catálogo (DB13)" />} />
                <Route path="/suppliers" element={<GenericList resource="suppliers" title="Proveedores (DB25)" />} />
                <Route path="/quotes" element={<GenericList resource="quotes" title="Cotizaciones (DB27)" />} />
                <Route path="/visits" element={<GenericList resource="sop-visits" title="Visitas SOP (DB42)" />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>
            </Routes>
            <UnsavedChangesNotifier />
          </Refine>
        </AntApp>
      </ConfigProvider>
    </BrowserRouter>
  );
}
