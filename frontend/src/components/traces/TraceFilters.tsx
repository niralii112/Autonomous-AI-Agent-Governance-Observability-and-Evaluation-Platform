type TraceFiltersProps = {
  search: string;
  onSearchChange: (search: string) => void;
  agentFilter: string;
  onAgentFilterChange: (agentId: string) => void;
  agents: Array<{ agent_id: string; agent_name: string }>;
  hasErrorFilter: string;
  onHasErrorFilterChange: (hasError: string) => void;
  windowMinutes: number;
  onWindowMinutesChange: (minutes: number) => void;
};

export default function TraceFilters({
  search,
  onSearchChange,
  agentFilter,
  onAgentFilterChange,
  agents,
  hasErrorFilter,
  onHasErrorFilterChange,
  windowMinutes,
  onWindowMinutesChange,
}: TraceFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-3xl border border-[#111111]/10 bg-[#FFF8F2] p-5 shadow-xs">
      {/* Search Input */}
      <div className="flex-1 min-w-[200px]">
        <label className="block text-[10px] font-black uppercase tracking-wider text-[#777777] mb-1">
          Search Trace ID or Operation
        </label>
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Filter by trace ID, span, or service..."
          className="w-full rounded-xl border border-[#111111]/20 bg-white px-3.5 py-2 text-xs font-medium text-[#111111] placeholder-[#888888] focus:border-[#111111] focus:outline-none"
        />
      </div>

      {/* Agent Selector */}
      <div className="min-w-[170px]">
        <label className="block text-[10px] font-black uppercase tracking-wider text-[#777777] mb-1">
          Governed Agent
        </label>
        <select
          value={agentFilter}
          onChange={(e) => onAgentFilterChange(e.target.value)}
          className="w-full rounded-xl border border-[#111111]/20 bg-white px-3 py-2 text-xs font-semibold text-[#111111] focus:border-[#111111] focus:outline-none cursor-pointer"
        >
          <option value="ALL">All Agents</option>
          {agents.map((agent) => (
            <option key={agent.agent_id} value={agent.agent_id}>
              {agent.agent_name}
            </option>
          ))}
        </select>
      </div>

      {/* Error Filter */}
      <div className="min-w-[130px]">
        <label className="block text-[10px] font-black uppercase tracking-wider text-[#777777] mb-1">
          Status Outcome
        </label>
        <select
          value={hasErrorFilter}
          onChange={(e) => onHasErrorFilterChange(e.target.value)}
          className="w-full rounded-xl border border-[#111111]/20 bg-white px-3 py-2 text-xs font-semibold text-[#111111] focus:border-[#111111] focus:outline-none cursor-pointer"
        >
          <option value="ALL">All Outcomes</option>
          <option value="OK">Success (OK)</option>
          <option value="ERROR">Errors Only</option>
        </select>
      </div>

      {/* Window Selector */}
      <div className="min-w-[130px]">
        <label className="block text-[10px] font-black uppercase tracking-wider text-[#777777] mb-1">
          Time Window
        </label>
        <select
          value={windowMinutes}
          onChange={(e) => onWindowMinutesChange(Number(e.target.value))}
          className="w-full rounded-xl border border-[#111111]/20 bg-white px-3 py-2 text-xs font-semibold text-[#111111] focus:border-[#111111] focus:outline-none cursor-pointer"
        >
          <option value={15}>Last 15 minutes</option>
          <option value={60}>Last 1 hour</option>
          <option value={360}>Last 6 hours</option>
          <option value={1440}>Last 24 hours</option>
        </select>
      </div>
    </div>
  );
}
