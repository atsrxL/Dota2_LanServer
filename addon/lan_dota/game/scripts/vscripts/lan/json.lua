-- Minimal output-only JSON. Never evaluate JSON received from players.
local M = {}
local function quote(s)
    return '"' .. tostring(s):gsub('[%z\1-\31\\"]', function(c)
        local known = {['"']='\\"', ['\\']='\\\\', ['\n']='\\n', ['\r']='\\r', ['\t']='\\t'}
        return known[c] or string.format('\\u%04x', string.byte(c))
    end) .. '"'
end
local function encode(v, depth)
    if depth > 12 then error('JSON nesting limit') end
    local t = type(v)
    if t == 'nil' then return 'null' end
    if t == 'boolean' then return v and 'true' or 'false' end
    if t == 'number' then
        if v ~= v or v == math.huge or v == -math.huge then return 'null' end
        return tostring(v)
    end
    if t == 'string' then return quote(v) end
    if t ~= 'table' then return quote(tostring(v)) end
    local count, max, array = 0, 0, true
    for k in pairs(v) do
        count = count + 1
        if type(k) ~= 'number' or k < 1 or k % 1 ~= 0 then array = false else max = math.max(max,k) end
    end
    local parts = {}
    if array and count == max then
        for i=1,max do parts[#parts+1] = encode(v[i],depth+1) end
        return '[' .. table.concat(parts,',') .. ']'
    end
    for k,x in pairs(v) do parts[#parts+1] = quote(k) .. ':' .. encode(x,depth+1) end
    table.sort(parts)
    return '{' .. table.concat(parts,',') .. '}'
end
function M.encode(v) return encode(v,0) end
return M
