import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";

export interface InvoiceLineItem {
  booking_id: string;
  facility_id: string;
  facility_name: string;
  date: string;
  price_paise: number;
}

export interface Invoice {
  invoice_id: string;
  period: string;
  total_paise: number;
  line_items: InvoiceLineItem[];
}

export function useMyInvoices(enabled: boolean) {
  return useQuery({
    queryKey: ["my-invoices"],
    queryFn: () => apiFetch<{ items: Invoice[] }>("/invoices/mine"),
    enabled,
  });
}
