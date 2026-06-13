import { useEffect, useState } from 'react';
import { Coffee, TrendingUp, AlertCircle, RefreshCw, BarChart3, Clock, Utensils, ReceiptText } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// @ts-ignore
const webapp = window.Telegram?.WebApp;

interface KpiData {
  val?: string;
  checks?: number;
  cls?: string;
  txt?: string;
  target?: string;
  accumulated?: string;
  remaining?: string;
  trafficBuffer?: number;
  pct?: number;
  monthLabel?: string;
}

interface TopRowData {
  name: string;
  qty: number;
  revenue: number;
  revenueFormatted: string;
  profit: number;
  profitFormatted: string;
  margin: number;
  marginClass: string;
}

interface PlRowData {
  label: string;
  monthVal: string | null;
  annualVal: string | null;
  src: string;
  cls: string;
  indent: boolean;
  small: boolean;
  isSection: boolean;
}

interface DashboardData {
  periodLabel: string;
  evotorStatus: string;
  evotorBadge: string;
  grossProfit: string;
  grossMargin: string;
  netProfit: string;
  netMargin: string;
  forecastValue: string;
  forecastMonth: string;
  forecastRange?: {
    low: string;
    high: string;
    lastYear: string;
  };
  cogsIsProxy?: boolean;
  overview: {
    wow: string;
    window: string;
    label_text: string;
  };
  kpis: {
    revenue: KpiData;
    avgCheck: KpiData;
    breakEven: KpiData;
  };
  topRows: TopRowData[];
  plTable: PlRowData[];
}

export default function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState('7д'); // 7д, сег, вч, мес

  useEffect(() => {
    if (webapp) {
      webapp.ready();
      webapp.expand();
      document.documentElement.style.setProperty('--tg-theme-bg-color', webapp.backgroundColor || '#121212');
      document.documentElement.style.setProperty('--tg-theme-text-color', webapp.textColor || '#ffffff');
    }
    
    fetchData(period);
  }, [period]);

  const fetchData = async (p: string) => {
    setLoading(true);
    setError(null);
    try {
      const initData = webapp?.initData || '';
      const response = await fetch(`/api/dashboard?period=${encodeURIComponent(p)}`, {
        headers: {
          'Authorization': `tma ${initData}`,
        }
      });
      
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error || 'Нет доступа. Откройте панель через команду /dashboard у бота.');
        }
        if (response.status === 503) {
          throw new Error('Сервис просыпается, повторите через минуту.');
        }
        throw new Error(`Ошибка загрузки: ${response.status}`);
      }
      
      const result = await response.json();
      setData(result);
      
      if (webapp?.HapticFeedback) {
        webapp.HapticFeedback.impactOccurred('light');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
      if (webapp?.HapticFeedback) {
        webapp.HapticFeedback.notificationOccurred('error');
      }
    } finally {
      setLoading(false);
    }
  };

  const syncEvotor = async () => {
    if (webapp?.HapticFeedback) webapp.HapticFeedback.impactOccurred('medium');
    try {
      const initData = webapp?.initData || '';
      const response = await fetch('/api/sync', {
        method: 'POST',
        headers: {
          'Authorization': `tma ${initData}`,
        }
      });
      if (response.ok) {
        if (webapp?.HapticFeedback) webapp.HapticFeedback.notificationOccurred('success');
        fetchData(period);
      } else {
        const body = await response.json().catch(() => null);
        if (webapp?.HapticFeedback) webapp.HapticFeedback.notificationOccurred('error');
        webapp?.showAlert?.(body?.error || body?.message || `Синхронизация не прошла (${response.status})`);
      }
    } catch (e) {
      console.error(e);
      if (webapp?.HapticFeedback) webapp.HapticFeedback.notificationOccurred('error');
    }
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[100dvh] p-6 text-center bg-zinc-950 text-white">
        <AlertCircle className="w-12 h-12 text-rose-500 mb-4" />
        <h2 className="text-xl font-bold mb-2">Ошибка доступа</h2>
        <p className="text-zinc-400 mb-6">{error}</p>
        <button 
          onClick={() => fetchData(period)}
          className="px-6 py-3 bg-zinc-800 rounded-xl font-medium active:scale-95 transition-transform"
        >
          Повторить
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-[100dvh] bg-[#09090b] text-zinc-100 font-sans pb-8 selection:bg-amber-500/30">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-[#09090b]/80 backdrop-blur-xl border-b border-zinc-800/50 px-4 py-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center shadow-lg shadow-amber-900/20">
              <Coffee className="w-5 h-5 text-amber-50" />
            </div>
            <div>
              <h1 className="text-lg font-bold leading-tight tracking-tight">Дарвин</h1>
              <p className="text-[11px] text-zinc-500 font-medium tracking-wide uppercase">
                {data?.evotorBadge || 'Загрузка...'}
              </p>
            </div>
          </div>
          <button 
            onClick={syncEvotor}
            className="w-10 h-10 rounded-full bg-zinc-800/50 flex items-center justify-center active:bg-zinc-700 transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4 text-zinc-400", loading && "animate-spin text-amber-500")} />
          </button>
        </div>

        {/* Period Tabs */}
        <div className="flex gap-1.5 mt-5 bg-zinc-900/60 p-1.5 rounded-2xl">
          {[
            { id: 'сег', label: 'Сегодня' },
            { id: 'вч', label: 'Вчера' },
            { id: '7д', label: 'Неделя' },
            { id: 'мес', label: 'Месяц' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => {
                setPeriod(tab.id);
                if (webapp?.HapticFeedback) webapp.HapticFeedback.selectionChanged();
              }}
              className={cn(
                "flex-1 py-1.5 text-xs sm:text-sm font-medium rounded-xl transition-all duration-200",
                period === tab.id 
                  ? "bg-zinc-700 text-white shadow-sm" 
                  : "text-zinc-500 hover:text-zinc-300"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </header>

      <main className="px-4 mt-6 space-y-5">
        {loading && !data ? (
          <div className="space-y-4 animate-pulse">
            <div className="h-32 bg-zinc-900/50 rounded-3xl"></div>
            <div className="grid grid-cols-2 gap-4">
              <div className="h-24 bg-zinc-900/50 rounded-3xl"></div>
              <div className="h-24 bg-zinc-900/50 rounded-3xl"></div>
            </div>
          </div>
        ) : data && (
          <>
            {/* Main KPI */}
            <div className="bg-gradient-to-br from-zinc-800 to-zinc-900 rounded-3xl p-5 border border-zinc-700/50 shadow-xl relative overflow-hidden">
              <div className="absolute top-0 right-0 p-4 opacity-[0.03]">
                <BarChart3 className="w-32 h-32" />
              </div>
              <p className="text-zinc-400 text-sm font-medium mb-1">Чистая прибыль ({data.periodLabel})</p>
              <div className="flex items-baseline gap-2 mb-5">
                <span className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-amber-200 to-amber-500">
                  {data.netProfit}₽
                </span>
              </div>
              
              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-zinc-700/50">
                <div>
                  <p className="text-[11px] text-zinc-500 mb-1 uppercase tracking-wider font-semibold">Валовая прибыль</p>
                  <p className="font-semibold text-zinc-200">{data.grossProfit}₽</p>
                </div>
                <div>
                  <p className="text-[11px] text-zinc-500 mb-1 uppercase tracking-wider font-semibold">Маржинальность</p>
                  <p className="font-semibold text-emerald-400">{data.netMargin}%</p>
                </div>
              </div>
            </div>

            {/* Forecast */}
            {data.forecastValue && data.forecastValue !== '—' && (
              <div className="bg-amber-950/20 border border-amber-900/30 rounded-3xl p-4 flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-amber-900/30 flex items-center justify-center shrink-0">
                  <TrendingUp className="w-6 h-6 text-amber-500" />
                </div>
                <div>
                  <p className="text-[11px] text-amber-600/80 font-bold uppercase tracking-wider mb-0.5">Прогноз на {data.forecastMonth}</p>
                  <p className="text-lg font-bold text-amber-100">{data.forecastValue}₽</p>
                  {data.forecastRange && (data.forecastRange.low !== '—' || data.forecastRange.high !== '—') && (
                    <p className="text-[10px] text-amber-600/60 mt-1.5">
                      диапазон: {data.forecastRange.low} — {data.forecastRange.high}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* React KPIs */}
            {data.kpis && (
              <div className="space-y-3">
                <h2 className="text-base font-bold flex items-center gap-2 pl-1">
                  <ReceiptText className="w-4 h-4 text-zinc-500" />
                  Чеки и Выручка
                </h2>
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2 bg-zinc-900/80 rounded-3xl p-4 border border-zinc-800/50 flex flex-col min-h-[106px] justify-between">
                    <div className="flex justify-between items-start w-full">
                      <div>
                        <div className="text-[11px] uppercase tracking-wider font-semibold text-zinc-500">Точка безубыточности</div>
                        <div className="text-xl font-bold my-1.5 text-blue-400">{data.kpis.breakEven.target}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-[11px] uppercase tracking-wider font-semibold text-zinc-500">Прогресс за {data.kpis.breakEven.monthLabel}</div>
                        <div className={cn("text-lg font-extrabold mt-1", (data.kpis.breakEven.pct || 0) >= 100 ? "text-emerald-500" : "text-blue-400")}>
                          {(data.kpis.breakEven.pct || 0).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                    
                    <div className="mt-2.5 w-full">
                      <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden relative">
                        <div 
                          className={cn("h-full rounded-full transition-all duration-300", (data.kpis.breakEven.pct || 0) >= 100 ? "bg-emerald-500" : "bg-blue-400")}
                          style={{ width: `${Math.min(100, data.kpis.breakEven.pct || 0)}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[11px] mt-2 font-medium">
                        <div className="text-zinc-400">Накоплено: <span className="text-zinc-200">{data.kpis.breakEven.accumulated}</span></div>
                        <div className="text-zinc-400">
                          {(data.kpis.breakEven.pct || 0) >= 100 ?
                            <span className="text-emerald-500 font-bold">🎯 Цель достигнута!</span> :
                            <span>Осталось: <span className="text-zinc-200">{data.kpis.breakEven.remaining || '—'}</span></span>
                          }
                        </div>
                      </div>
                      {data.kpis.breakEven.trafficBuffer !== undefined && (
                        <div className="text-[10px] text-zinc-500 mt-1.5">
                          Запас по трафику: {data.kpis.breakEven.trafficBuffer < 0 ? '−' : '+'}{Math.abs(data.kpis.breakEven.trafficBuffer).toFixed(1)}%
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="bg-zinc-900/80 rounded-3xl p-4 border border-zinc-800/50 flex flex-col">
                    <div className="text-[11px] uppercase tracking-wider font-semibold text-zinc-500">Выручка</div>
                    <div className="text-xl font-bold my-1.5 text-amber-400">{data.kpis.revenue.val}</div>
                    <div className={cn("text-[11px] font-medium", data.kpis.revenue.cls === 'up' ? 'text-emerald-500' : 'text-rose-500')}>
                      {data.kpis.revenue.txt}
                    </div>
                    <div className="text-[10px] text-zinc-600 mt-1">
                      {data.overview.label_text} · {data.kpis.revenue.checks} чеков
                    </div>
                    {data.overview.wow && data.overview.wow !== 'нет сравнения' && (
                      <div className="text-[10px] text-blue-400 mt-1.5 font-medium">
                        WoW: {data.overview.wow}
                      </div>
                    )}
                  </div>

                  <div className="bg-zinc-900/80 rounded-3xl p-4 border border-zinc-800/50 flex flex-col">
                    <div className="text-[11px] uppercase tracking-wider font-semibold text-zinc-500">Средний чек</div>
                    <div className="text-xl font-bold my-1.5 text-white">{data.kpis.avgCheck.val}</div>
                    <div className={cn("text-[11px] font-medium", data.kpis.avgCheck.cls === 'up' ? 'text-emerald-500' : 'text-rose-500')}>
                      {data.kpis.avgCheck.txt}
                    </div>
                    <div className="text-[10px] text-zinc-600 mt-1.5">{data.kpis.revenue.checks} чеков за {data.overview.label_text}</div>
                  </div>
                </div>
              </div>
            )}

            {/* React Top Rows */}
            {data.topRows && data.topRows.length > 0 && (
              <div className="space-y-3">
                <h2 className="text-base font-bold flex items-center gap-2 pl-1">
                  <Utensils className="w-4 h-4 text-zinc-500" />
                  Топ товаров
                </h2>
                <div className="bg-zinc-900/80 rounded-3xl p-1 border border-zinc-800/50 overflow-x-auto">
                  <table className="w-full text-left text-sm whitespace-nowrap">
                    <tbody>
                      {data.topRows.map((row, i) => (
                        <tr key={i} className="border-b border-zinc-800/30 last:border-0">
                          <td className="p-3.5 font-medium text-zinc-200">{row.name}</td>
                          <td className="p-3.5 text-right text-zinc-400">{row.qty} шт</td>
                          <td className="p-3.5 text-right">{row.revenueFormatted}</td>
                          <td className="p-3.5 text-right text-emerald-400">{row.profitFormatted}</td>
                          <td className="p-3.5 text-right">
                            <div className="flex items-center gap-2.5 justify-end w-24 ml-auto">
                              <div className="flex-1 h-1.5 bg-zinc-800/80 rounded-full overflow-hidden">
                                <div 
                                  className={cn("h-full rounded-full", row.marginClass === 'g' ? 'bg-emerald-500' : (row.marginClass === 'o' ? 'bg-rose-500' : 'bg-amber-500'))}
                                  style={{ width: `${Math.min(100, row.margin)}%` }}
                                />
                              </div>
                              <span className="text-[11px] font-semibold w-8 text-left">{row.margin}%</span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            
            {/* React P&L */}
            {data.plTable && (
              <div className="space-y-3 pb-8">
                <h2 className="text-base font-bold flex items-center gap-2 pl-1">
                  <Clock className="w-4 h-4 text-zinc-500" />
                  P&L Отчет
                </h2>
                <div className="bg-zinc-900/80 rounded-3xl p-4.5 border border-zinc-800/50 text-sm overflow-hidden">
                  <div className="flex justify-between items-center py-2.5 border-b border-zinc-800/30">
                    <div className="flex-[1.5] text-[10px] uppercase tracking-wider text-zinc-500 font-semibold pb-1">Статья</div>
                    <div className="flex-1 text-[10px] uppercase tracking-wider text-zinc-500 font-semibold text-right pb-1">{data.periodLabel}</div>
                    <div className="flex-1 text-[10px] uppercase tracking-wider text-zinc-500 font-semibold text-right pb-1">12 мес · факт</div>
                  </div>
                  
                  {data.plTable.map((row, i) => {
                    if (row.isSection) {
                      return (
                        <div key={i} className="flex justify-between items-center py-2.5 border-b border-zinc-800/30 text-amber-500/90 font-bold pt-5 pb-1">
                          <div className="flex-[1.5]">{row.label}</div>
                          <div className="flex-1"></div>
                          <div className="flex-1"></div>
                        </div>
                      );
                    }
                    
                    return (
                      <div key={i} className={cn("flex justify-between items-center py-2.5 border-b border-zinc-800/30 last:border-0", 
                        row.cls.includes('subtotal') && "font-bold",
                        row.cls.includes('total') && "font-black text-base pt-5 pb-1 border-t-2 border-zinc-800"
                      )}>
                        <div className={cn("flex-[1.5]", row.indent && "pl-7", row.small && "text-[11px] text-zinc-500")}>
                          {row.label}
                        </div>
                        <div className={cn("flex-1 text-right", 
                          row.cls.includes('v-pos') && "text-emerald-400",
                          row.cls.includes('v-neg') && "text-rose-400/90",
                          row.cls.includes('v-gold') && "text-amber-400",
                          row.cls.includes('v-muted') && "text-zinc-600"
                        )}>
                          {row.monthVal || <span className="text-zinc-600">—</span>}
                        </div>
                        <div className={cn("flex-1 text-right",
                          row.cls.includes('v-pos') && "text-emerald-400",
                          row.cls.includes('v-neg') && "text-rose-400/90",
                          row.cls.includes('v-gold') && "text-amber-400",
                          row.cls.includes('v-muted') && "text-zinc-600"
                        )}>
                          {row.annualVal || <span className="text-zinc-600">—</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
