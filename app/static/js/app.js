const uiState = {
    isTesting: false,
    lockedAddress: '',
    proxyPage: 1,
    proxyTotalPages: 1,
    proxyRefreshTick: 0,
    dirty: {
        main: false,
        socks5: false,
        http: false
    },
    syncing: false,
    statusTimer: null,
    countriesLoaded: false
};

const FORM_FIELDS = {
    main: ['proxy-type', 'country', 'source-filter', 'status-filter', 'sort-by', 'sort-order', 'page-size', 'test-count', 'fetch-limit', 'test-interval', 'rotate-interval'],
    socks5: ['socks5-enabled', 'socks5-port-config', 'socks5-auth-enabled', 'socks5-user', 'socks5-pass'],
    http: ['http-enabled', 'http-port-config', 'http-auth-enabled', 'http-user', 'http-pass']
};

document.addEventListener('DOMContentLoaded', () => {
    bindUi();
    bindModuleTabs();
    loadAll(true);
    setInterval(() => {
        loadStats();
        loadConnection();
    }, 5000);
    setInterval(() => {
        loadTopProxies();
        loadSubscriptionStats();
        uiState.proxyRefreshTick += 1;
        if (uiState.proxyRefreshTick % 2 === 0) {
            loadProxies();
        }
    }, 15000);
    setInterval(() => {
        loadFavorites();
        loadSubscriptions();
        loadSocks5Config(false);
        loadHttpProxyConfig(false);
    }, 30000);
});

function bindUi() {
    bindDirtyTracking('main');
    bindDirtyTracking('socks5');
    bindDirtyTracking('http');

    document.getElementById('socks5-auth-enabled').addEventListener('change', () => {
        toggleAuthConfig('socks5');
        updateSocks5ConnectionPreview();
    });
    document.getElementById('http-auth-enabled').addEventListener('change', () => {
        toggleAuthConfig('http');
        updateHttpConnectionPreview();
    });

    ['proxy-type', 'country', 'source-filter', 'status-filter', 'sort-by', 'sort-order', 'page-size'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            uiState.proxyPage = 1;
            loadProxies();
        });
    });

    ['socks5-port-config', 'socks5-user', 'socks5-pass'].forEach(id => {
        document.getElementById(id).addEventListener('input', updateSocks5ConnectionPreview);
    });
    ['http-port-config', 'http-user', 'http-pass'].forEach(id => {
        document.getElementById(id).addEventListener('input', updateHttpConnectionPreview);
    });
}

function bindModuleTabs() {
    const tabs = document.querySelectorAll('.module-tab');
    const sections = document.querySelectorAll('.module-section');
    if (!tabs.length || !sections.length) {
        return;
    }

    const activate = (tabName) => {
        tabs.forEach(tab => tab.classList.toggle('is-active', tab.dataset.tab === tabName));
        sections.forEach(section => section.classList.toggle('is-active', section.dataset.section === tabName));
    };

    tabs.forEach(tab => {
        tab.addEventListener('click', () => activate(tab.dataset.tab));
    });

    activate('overview');
}

function bindDirtyTracking(formKey) {
    for (const id of FORM_FIELDS[formKey]) {
        const element = document.getElementById(id);
        if (!element) {
            continue;
        }
        const handler = () => {
            if (uiState.syncing) {
                return;
            }
            setDirty(formKey, true);
        };
        element.addEventListener('input', handler);
        element.addEventListener('change', handler);
    }
}

function setDirty(formKey, dirty) {
    uiState.dirty[formKey] = dirty;
    const hint = document.getElementById(`${formKey}-dirty-hint`);
    if (hint) {
        hint.classList.toggle('hidden', !dirty);
    }
}

function withSync(fn) {
    uiState.syncing = true;
    try {
        fn();
    } finally {
        uiState.syncing = false;
    }
}

function isFormBeingEdited(formKey) {
    const active = document.activeElement;
    if (!active || !active.id) {
        return false;
    }
    return FORM_FIELDS[formKey].includes(active.id);
}

function shouldSkipEditableSync(formKey, force = false) {
    if (force) {
        return false;
    }
    return uiState.dirty[formKey] || isFormBeingEdited(formKey);
}

async function loadAll(force = false) {
    await Promise.all([
        loadCountries(),
        loadConfig(force),
        loadStats(),
        loadConnection(),
        loadProxies(),
        loadFavorites(),
        loadSocks5Config(force),
        loadHttpProxyConfig(force),
        loadSubscriptions(),
        loadSubscriptionStats(),
        loadTopProxies()
    ]);
}

async function api(path, options = {}) {
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.message || '请求失败');
    }
    return data;
}

function setPageStatus(text) {
    document.getElementById('page-status').textContent = text;
}

function showStatus(message, type = 'info') {
    const box = document.getElementById('status-message');
    const text = document.getElementById('status-text');
    text.textContent = message;
    box.className = `alert alert-${type}`;
    box.style.display = 'flex';
    clearTimeout(uiState.statusTimer);
    uiState.statusTimer = setTimeout(() => {
        box.style.display = 'none';
    }, 5000);
}

function setButtonLoading(id, loading, idleText, loadingText) {
    const button = document.getElementById(id);
    if (!button) {
        return;
    }
    button.disabled = loading;
    button.innerHTML = loading ? `<span class="spinner"></span> ${loadingText}` : idleText;
}

async function loadCountries() {
    if (uiState.countriesLoaded) {
        return;
    }
    try {
        const data = await api('/api/countries');
        const select = document.getElementById('country');
        const currentValue = select.value;
        const options = ['<option value="">全部国家</option>'];
        for (const code of data.countries || []) {
            options.push(`<option value="${code}">${code}</option>`);
        }
        select.innerHTML = options.join('');
        select.value = currentValue || '';
        uiState.countriesLoaded = true;
    } catch (error) {
        console.error('加载国家列表失败:', error);
    }
}

async function loadConfig(force = false) {
    try {
        const data = await api('/api/config');
        const config = data.config;
        if (!shouldSkipEditableSync('main', force)) {
            withSync(() => {
                document.getElementById('proxy-type').value = config.protocol || config.type || 'all';
                document.getElementById('country').value = config.country || '';
                document.getElementById('test-count').value = config.test_count || 50;
                document.getElementById('test-interval').value = config.test_interval || 60;
                document.getElementById('rotate-interval').value = config.rotate_interval || 300;
                document.getElementById('fetch-limit').value = config.fetch_limit || 50;
            });
            setDirty('main', false);
        }
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

async function saveConfig() {
    const payload = {
        type: document.getElementById('proxy-type').value,
        protocol: document.getElementById('proxy-type').value,
        country: document.getElementById('country').value,
        test_count: parseInt(document.getElementById('test-count').value, 10),
        fetch_limit: parseInt(document.getElementById('fetch-limit').value, 10),
        test_interval: parseInt(document.getElementById('test-interval').value, 10),
        rotate_interval: parseInt(document.getElementById('rotate-interval').value, 10)
    };

    setButtonLoading('btn-save-main', true, '保存筛选配置', '保存中...');
    setPageStatus('保存配置中');
    try {
        await api('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        setDirty('main', false);
        showStatus('筛选配置已保存', 'info');
        await Promise.all([loadConfig(true), loadProxies(), loadConnection()]);
        setPageStatus('就绪');
    } catch (error) {
        showStatus(`保存失败：${error.message}`, 'warning');
        setPageStatus('保存失败');
    } finally {
        setButtonLoading('btn-save-main', false, '保存筛选配置', '保存中...');
    }
}

async function fetchProxies() {
    setButtonLoading('btn-fetch', true, '获取代理', '获取中...');
    setPageStatus('拉取代理中');
    try {
        const data = await api('/api/proxies/fetch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: document.getElementById('proxy-type').value,
                country: document.getElementById('country').value,
                fetch_limit: parseInt(document.getElementById('fetch-limit').value, 10)
            })
        });
        showStatus(data.message, 'info');
        await Promise.all([loadStats(), loadProxies(), loadCountries(), loadSubscriptionStats()]);
        setPageStatus('就绪');
    } catch (error) {
        showStatus(`获取失败：${error.message}`, 'warning');
        setPageStatus('获取失败');
    } finally {
        setButtonLoading('btn-fetch', false, '获取代理', '获取中...');
    }
}

async function testProxies() {
    if (uiState.isTesting) {
        return;
    }
    uiState.isTesting = true;
    setButtonLoading('btn-test', true, '开始测速', '测速中...');
    setPageStatus('测速中');
    try {
        const data = await api('/api/proxies/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                count: parseInt(document.getElementById('test-count').value, 10),
                protocol: document.getElementById('proxy-type').value,
                country: document.getElementById('country').value
            })
        });
        showStatus(`测试完成：${data.working}/${data.tested} 可用`, 'info');
        await Promise.all([loadStats(), loadProxies(), loadConnection(), loadSubscriptionStats()]);
        setPageStatus('就绪');
    } catch (error) {
        showStatus(`测试失败：${error.message}`, 'warning');
        setPageStatus('测速失败');
    } finally {
        uiState.isTesting = false;
        setButtonLoading('btn-test', false, '开始测速', '测速中...');
    }
}

async function testSingleProxy(address) {
    try {
        setPageStatus('单节点测速中');
        const data = await api('/api/proxies/test-one', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ address })
        });
        showStatus(`节点已测速：${data.proxy.address}`, 'info');
        await Promise.all([loadProxies(), loadStats(), loadSubscriptionStats()]);
        setPageStatus('就绪');
    } catch (error) {
        showStatus(`节点测速失败：${error.message}`, 'warning');
        setPageStatus('测速失败');
    }
}

async function loadStats() {
    try {
        const data = await api('/api/stats');
        const stats = data.stats;
        document.getElementById('stat-total').textContent = stats.total_fetched;
        document.getElementById('stat-working').textContent = stats.working_count;
        document.getElementById('stat-latency').textContent = stats.avg_latency ? Math.round(stats.avg_latency) : '-';
        document.getElementById('stat-tested').textContent = stats.total_tested;
        document.getElementById('last-update').textContent = stats.last_update ? new Date(stats.last_update).toLocaleString('zh-CN') : '-';
        document.getElementById('stat-fetch-error').textContent = stats.last_fetch_error || '无';
        document.getElementById('stat-test-error').textContent = stats.last_test_error || '无';
        uiState.isTesting = !!stats.is_testing;
    } catch (error) {
        console.error('加载统计失败:', error);
    }
}

async function loadConnection() {
    try {
        const data = await api('/api/connection');
        const info = data.connection;
        document.getElementById('stat-connection-status').textContent = info.connected ? '已连接' : '未连接';
        uiState.lockedAddress = info.locked && info.preferred ? (info.preferred.address || '') : '';
        document.getElementById('stat-lock-status').textContent = info.locked && info.preferred && info.preferred.address
            ? `已锁定：${info.preferred.address}`
            : '未锁定';
        document.getElementById('btn-unlock-proxy').disabled = !(info.locked && info.preferred && info.preferred.address);
        document.getElementById('btn-disconnect-main').disabled = !info.connected;
        if (info.proxy) {
            const proxy = info.proxy;
            document.getElementById('stat-connection-proxy').textContent = `${proxy.ip}:${proxy.port} (${(proxy.protocol || '').toUpperCase()})`;
            document.getElementById('stat-connection-extra').textContent = `${proxy.country || '-'} · ${proxy.speed_ms ? Math.round(proxy.speed_ms) + 'ms' : '-'} · ${info.locked ? '锁定中' : '自动'}`;
        } else {
            document.getElementById('stat-connection-proxy').textContent = '-';
            document.getElementById('stat-connection-extra').textContent = info.locked ? '未连接 · 锁定中' : '-';
        }
    } catch (error) {
        console.error('加载连接信息失败:', error);
    }
}

async function loadTopProxies() {
    try {
        const data = await api('/api/proxies/top?limit=10');
        renderTopProxyTable(data.items || []);
    } catch (error) {
        console.error('加载快捷代理失败:', error);
    }
}

function renderTopProxyTable(items) {
    const body = document.getElementById('top-proxy-tbody');
    if (!body) return;
    if (!items.length) {
        body.innerHTML = '<tr><td colspan="7" class="empty-state"><p>暂无可用节点</p></td></tr>';
        return;
    }

    body.innerHTML = items.map(item => {
        const latency = item.speed_ms == null ? '-' : Math.round(item.speed_ms);
        const statusText = item.is_working ? '可用' : '失败';
        const statusClass = item.is_working ? 'status-working' : 'status-failed';
        return `
            <tr>
                <td><code>${item.ip}:${item.port}</code></td>
                <td>${item.country || '-'}</td>
                <td>${latency}</td>
                <td>${item.source || '-'}</td>
                <td>${(item.protocol || '-').toUpperCase()}</td>
                <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                <td>
                    <button class="table-action" onclick='connectCurrentProxy(${JSON.stringify(item.address)})'>选用</button>
                    <button class="table-action" onclick='testSingleProxy(${JSON.stringify(item.address)})'>测速</button>
                </td>
            </tr>
        `;
    }).join('');
}

async function loadProxies() {
    try {
        const protocol = document.getElementById('proxy-type').value;
        const country = document.getElementById('country').value;
        const source = document.getElementById('source-filter').value;
        const status = document.getElementById('status-filter').value;
        const sortBy = document.getElementById('sort-by').value;
        const sortOrder = document.getElementById('sort-order').value;
        const pageSize = document.getElementById('page-size').value;
        const data = await api(`/api/proxies?working=false&page=${uiState.proxyPage}&page_size=${encodeURIComponent(pageSize)}&protocol=${encodeURIComponent(protocol)}&country=${encodeURIComponent(country)}&source=${encodeURIComponent(source)}&status=${encodeURIComponent(status)}&sort_by=${encodeURIComponent(sortBy)}&sort_order=${encodeURIComponent(sortOrder)}`);
        uiState.proxyPage = data.page || 1;
        uiState.proxyTotalPages = data.total_pages || 1;
        document.getElementById('proxy-count').textContent = data.filtered_count ?? data.count;
        document.getElementById('proxy-page-current').textContent = uiState.proxyPage;
        document.getElementById('proxy-page-total').textContent = uiState.proxyTotalPages;
        document.getElementById('proxy-filtered-count').textContent = data.filtered_count ?? 0;
        document.getElementById('proxy-source-count').textContent = (data.sources || []).length;
        document.getElementById('btn-page-prev').disabled = uiState.proxyPage <= 1;
        document.getElementById('btn-page-next').disabled = uiState.proxyPage >= uiState.proxyTotalPages;
        renderProxyTable(data.proxies || []);
        document.getElementById('stat-total').textContent = data.total_fetched ?? data.count ?? 0;
        fillSourceFilter(data.sources || []);
    } catch (error) {
        console.error('加载代理列表失败:', error);
    }
}

function fillSourceFilter(sources) {
    const select = document.getElementById('source-filter');
    if (!select) return;
    const current = select.value;
    const options = ['<option value="">全部订阅</option>'];
    const values = [];
    for (const source of (sources || [])) {
        const value = typeof source === 'string' ? source : source.value;
        const label = typeof source === 'string' ? source : (source.label || source.value);
        if (!value) continue;
        values.push(value);
        options.push(`<option value="${value}">${label}</option>`);
    }
    select.innerHTML = options.join('');
    if (values.includes(current)) {
        select.value = current;
    } else {
        select.value = '';
    }
}

function changeProxyPage(step) {
    const nextPage = uiState.proxyPage + step;
    if (nextPage < 1 || nextPage > uiState.proxyTotalPages) {
        return;
    }
    uiState.proxyPage = nextPage;
    loadProxies();
}

function renderProxyTable(proxies) {
    const body = document.getElementById('proxy-tbody');
    if (!proxies.length) {
        body.innerHTML = '<tr><td colspan="8" class="empty-state"><div class="empty-state-icon">[]</div><p>暂无节点</p><p class="small" style="margin-top:10px;">这个池子默认是空的，先加订阅再拉取</p></td></tr>';
        return;
    }

    proxies.sort((left, right) => {
        if (left.speed_ms == null) return 1;
        if (right.speed_ms == null) return -1;
        return left.speed_ms - right.speed_ms;
    });

    body.innerHTML = proxies.map(proxy => {
        const latency = proxy.speed_ms == null ? '-' : Math.round(proxy.speed_ms);
        const latencyClass = getLatencyClass(proxy.speed_ms);
        const disabled = proxy.is_working ? '' : 'disabled';
        const testDisabled = uiState.isTesting ? 'disabled' : '';
        const isLocked = uiState.lockedAddress === proxy.address;
        return `
            <tr>
                <td><code>${proxy.ip}:${proxy.port}</code></td>
                <td>${(proxy.protocol || '-').toUpperCase()}</td>
                <td>${proxy.country || '-'}</td>
                <td>${proxy.anonymity || '-'}</td>
                <td class="${latencyClass}">${latency}</td>
                <td><span class="status-badge ${proxy.is_working ? 'status-working' : 'status-failed'}">${proxy.is_working ? '可用' : '失败'}</span></td>
                <td>${proxy.last_tested ? new Date(proxy.last_tested).toLocaleString('zh-CN') : '-'}</td>
                <td>
                    <button class="table-action" ${disabled} onclick='connectCurrentProxy(${JSON.stringify(proxy.address)})'>连接</button>
                    <button class="table-action" ${testDisabled} onclick='testSingleProxy(${JSON.stringify(proxy.address)})'>测速</button>
                    <button class="table-action ${isLocked ? 'is-active' : ''}" ${disabled} onclick='setPreferredProxy(${JSON.stringify(proxy.address)})'>${isLocked ? '已锁定' : '锁定'}</button>
                    <button class="table-action secondary" onclick='toggleFavorite(${JSON.stringify(proxy.address)}, ${JSON.stringify(proxy.protocol || '')}, ${JSON.stringify(proxy.country || '')}, ${JSON.stringify(proxy.speed_ms)}, ${JSON.stringify(proxy.last_tested)})'>收藏</button>
                </td>
            </tr>`;
    }).join('');
}

async function loadFavorites() {
    try {
        const data = await api('/api/favorites');
        renderFavoriteTable(data.favorites || []);
    } catch (error) {
        console.error('加载收藏失败:', error);
    }
}

function renderFavoriteTable(items) {
    const body = document.getElementById('favorite-tbody');
    document.getElementById('favorite-count').textContent = items.length;
    if (!items.length) {
        body.innerHTML = '<tr><td colspan="6" class="empty-state"><div class="empty-state-icon">*</div><p>暂无收藏</p><p class="small" style="margin-top:10px;">在代理列表中点击收藏</p></td></tr>';
        return;
    }

    body.innerHTML = items.map(item => `
        <tr>
            <td><code>${item.address}</code></td>
            <td>${(item.protocol || '-').toUpperCase()}</td>
            <td>${item.country || '-'}</td>
            <td>${item.latency == null ? '-' : Math.round(item.latency)}</td>
            <td>${item.last_tested ? new Date(item.last_tested).toLocaleString('zh-CN') : '-'}</td>
            <td>
                <button class="table-action" onclick='connectCurrentProxy(${JSON.stringify(item.address)})'>连接</button>
                <button class="table-action ${uiState.lockedAddress === item.address ? 'is-active' : ''}" onclick='setPreferredProxy(${JSON.stringify(item.address)})'>${uiState.lockedAddress === item.address ? '已锁定' : '锁定'}</button>
                <button class="table-action secondary" onclick='removeFavorite(${JSON.stringify(item.address)})'>移除</button>
            </td>
        </tr>`).join('');
}

async function toggleFavorite(address, protocol, country, latency, lastTested) {
    try {
        await api('/api/favorites', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ address, protocol, country, latency, last_tested: lastTested })
        });
        showStatus(`已收藏 ${address}`, 'info');
        loadFavorites();
    } catch (error) {
        showStatus(`收藏失败：${error.message}`, 'warning');
    }
}

async function removeFavorite(address) {
    try {
        await api(`/api/favorites?address=${encodeURIComponent(address)}`, { method: 'DELETE' });
        showStatus(`已移除 ${address}`, 'info');
        loadFavorites();
    } catch (error) {
        showStatus(`移除失败：${error.message}`, 'warning');
    }
}

async function setPreferredProxy(address) {
    try {
        const data = await api('/api/preferred', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ address })
        });
        showStatus(data.message || `已锁定代理 ${address}`, 'info');
        await loadConnection();
        await loadProxies();
    } catch (error) {
        showStatus(`锁定失败：${error.message}`, 'warning');
    }
}

async function clearPreferredProxy() {
    try {
        const data = await api('/api/preferred', { method: 'DELETE' });
        showStatus(data.message || '已解除锁定代理', 'info');
        await loadConnection();
        await loadProxies();
    } catch (error) {
        showStatus(`解除锁定失败：${error.message}`, 'warning');
    }
}

async function connectCurrentProxy(address = '') {
    try {
        const payload = address ? { address } : {};
        const data = await api('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        showStatus(data.message || '连接成功', 'info');
        await loadConnection();
        await loadProxies();
    } catch (error) {
        showStatus(`连接失败：${error.message}`, 'warning');
    }
}

async function disconnectCurrentProxy() {
    try {
        const data = await api('/api/connect', { method: 'DELETE' });
        showStatus(data.message || '已断开当前代理', 'info');
        await loadConnection();
        await loadProxies();
    } catch (error) {
        showStatus(`断开失败：${error.message}`, 'warning');
    }
}

function getLatencyClass(latency) {
    if (latency == null) return '';
    if (latency < 500) return 'latency-good';
    if (latency < 1500) return 'latency-medium';
    return 'latency-bad';
}

function toggleAuthConfig(type) {
    const enabled = document.getElementById(`${type}-auth-enabled`).value === 'true';
    document.getElementById(`${type}-auth-config`).style.display = enabled ? 'grid' : 'none';
}

function updateSocks5ConnectionPreview() {
    const port = document.getElementById('socks5-port-config').value || '5001';
    const authEnabled = document.getElementById('socks5-auth-enabled').value === 'true';
    const username = document.getElementById('socks5-user').value || 'username';
    const password = document.getElementById('socks5-pass').value || 'password';
    document.getElementById('socks5-connection-info').textContent = `socks5://${authEnabled ? `${username}:${password}@` : ''}localhost:${port}`;
}

function updateHttpConnectionPreview() {
    const port = document.getElementById('http-port-config').value || '5002';
    const authEnabled = document.getElementById('http-auth-enabled').value === 'true';
    const username = document.getElementById('http-user').value || 'username';
    const password = document.getElementById('http-pass').value || 'password';
    document.getElementById('http-connection-info').textContent = `http://${authEnabled ? `${username}:${password}@` : ''}localhost:${port}`;
}

async function loadSocks5Config(force = false) {
    try {
        const [configData, statsData, runtimeData] = await Promise.all([api('/api/config/socks5'), api('/api/socks5'), api('/api/stats')]);
        const config = configData.config;
        const stats = statsData.socks5;
        const runtime = runtimeData.stats?.socks5_runtime || {};

        document.getElementById('socks5-status').value = config.enabled ? (runtime.running ? '运行中' : `未运行${runtime.last_error ? '：' + runtime.last_error : ''}`) : '已禁用';
        document.getElementById('socks5-connections').textContent = stats.connections || 0;

        if (!shouldSkipEditableSync('socks5', force)) {
            withSync(() => {
                document.getElementById('socks5-enabled').value = String(!!config.enabled);
                document.getElementById('socks5-port-config').value = config.port;
                document.getElementById('socks5-auth-enabled').value = String(!!config.auth_enabled);
                document.getElementById('socks5-user').value = config.username || '';
                document.getElementById('socks5-pass').value = config.password || '';
            });
            setDirty('socks5', false);
        }

        toggleAuthConfig('socks5');
        updateSocks5ConnectionPreview();
    } catch (error) {
        console.error('加载 SOCKS5 配置失败:', error);
    }
}

async function saveSocks5Config() {
    const payload = {
        enabled: document.getElementById('socks5-enabled').value === 'true',
        port: parseInt(document.getElementById('socks5-port-config').value, 10),
        auth_enabled: document.getElementById('socks5-auth-enabled').value === 'true',
        username: document.getElementById('socks5-user').value,
        password: document.getElementById('socks5-pass').value
    };
    setButtonLoading('btn-save-socks5', true, '保存配置', '保存中...');
    try {
        const data = await api('/api/config/socks5', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        setDirty('socks5', false);
        showStatus(data.message, 'info');
        await loadSocks5Config(true);
    } catch (error) {
        showStatus(`保存失败：${error.message}`, 'warning');
    } finally {
        setButtonLoading('btn-save-socks5', false, '保存配置', '保存中...');
    }
}

async function restartSocks5() {
    try {
        const data = await api('/api/restart/socks5', { method: 'POST' });
        showStatus(data.message, 'info');
        loadSocks5Config(true);
    } catch (error) {
        showStatus(`操作失败：${error.message}`, 'warning');
    }
}

async function loadHttpProxyConfig(force = false) {
    try {
        const [configData, statsData, runtimeData] = await Promise.all([api('/api/config/http-proxy'), api('/api/http-proxy'), api('/api/stats')]);
        const config = configData.config;
        const stats = statsData.http_proxy;
        const runtime = runtimeData.stats?.http_runtime || {};

        document.getElementById('http-status').value = config.enabled ? (runtime.running ? '运行中' : `未运行${runtime.last_error ? '：' + runtime.last_error : ''}`) : '已禁用';
        document.getElementById('http-requests').textContent = stats.requests_handled || 0;

        if (!shouldSkipEditableSync('http', force)) {
            withSync(() => {
                document.getElementById('http-enabled').value = String(!!config.enabled);
                document.getElementById('http-port-config').value = config.port;
                document.getElementById('http-auth-enabled').value = String(!!config.auth_enabled);
                document.getElementById('http-user').value = config.username || '';
                document.getElementById('http-pass').value = config.password || '';
            });
            setDirty('http', false);
        }

        toggleAuthConfig('http');
        updateHttpConnectionPreview();
    } catch (error) {
        console.error('加载 HTTP 配置失败:', error);
    }
}

async function saveHttpConfig() {
    const payload = {
        enabled: document.getElementById('http-enabled').value === 'true',
        port: parseInt(document.getElementById('http-port-config').value, 10),
        auth_enabled: document.getElementById('http-auth-enabled').value === 'true',
        username: document.getElementById('http-user').value,
        password: document.getElementById('http-pass').value
    };
    setButtonLoading('btn-save-http', true, '保存配置', '保存中...');
    try {
        const data = await api('/api/config/http-proxy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        setDirty('http', false);
        showStatus(data.message, 'info');
        await loadHttpProxyConfig(true);
    } catch (error) {
        showStatus(`保存失败：${error.message}`, 'warning');
    } finally {
        setButtonLoading('btn-save-http', false, '保存配置', '保存中...');
    }
}

async function restartHttpProxy() {
    try {
        const data = await api('/api/restart/http-proxy', { method: 'POST' });
        showStatus(data.message, 'info');
        loadHttpProxyConfig(true);
    } catch (error) {
        showStatus(`操作失败：${error.message}`, 'warning');
    }
}

function copyText(id) {
    const text = document.getElementById(id).textContent;
    navigator.clipboard.writeText(text)
        .then(() => showStatus('已复制到剪贴板', 'info'))
        .catch(() => showStatus('复制失败，请手动复制', 'warning'));
}

function showSocks5Help() {
    const info = document.getElementById('socks5-connection-info').textContent;
    alert(`SOCKS5 使用示例:\n\n${info}\n\ncurl --socks5-hostname 127.0.0.1:${document.getElementById('socks5-port-config').value} https://api.ipify.org`);
}

function renderSubscriptionList(subs) {
    const box = document.getElementById('subscription-list');
    if (!box) return;
    if (!subs || !subs.length) {
        box.innerHTML = '<div class="subscription-empty">还没有自定义订阅地址</div>';
        return;
    }
    box.innerHTML = subs.map(sub => {
        const name = sub.name || sub.url.split('/').pop() || sub.url;
        const host = (() => { try { return new URL(sub.url).hostname; } catch(e) { return sub.url; } })();
        return `
        <div class="subscription-item">
            <div>
                <div><strong>${name}</strong></div>
                <div class="small">来源：${host} · 间隔：${sub.interval || 60}s</div>
            </div>
            <div class="subscription-actions">
                <button class="table-action" onclick='editSubscription(${JSON.stringify(sub.name)},${JSON.stringify(sub.source)},${JSON.stringify(sub.interval)},${JSON.stringify(sub.url)})'>编辑</button>
                <button class="table-action secondary" onclick='removeSubscription(${JSON.stringify(sub.url)})'>删除</button>
            </div>
        </div>`;
    }).join('');
}

async function loadSubscriptions() {
    try {
        const data = await api('/api/subscriptions');
        uiState.subscriptionUrls = data.subscriptions || [];
        renderSubscriptionList(uiState.subscriptionUrls);
    } catch (error) {
        console.error('加载订阅失败:', error);
    }
}

function renderSubscriptionStats(stats) {
    const items = (stats && stats.sources) ? stats.sources : [];
    document.getElementById('stat-sub-total').textContent = (stats && Number.isFinite(stats.total)) ? stats.total : 0;
    document.getElementById('stat-sub-working').textContent = (stats && Number.isFinite(stats.available)) ? stats.available : 0;
    renderSubscriptionList(uiState.subscriptionUrls || []);
}

async function loadSubscriptionStats() {
    try {
        const data = await api('/api/subscriptions/stats');
        renderSubscriptionStats(data.stats || { total: 0, available: 0, sources: [] });
    } catch (error) {
        console.error('加载订阅统计失败:', error);
        renderSubscriptionStats({ total: 0, available: 0, sources: [] });
    }
}

function setSubscriptionFormMode(mode) {
    const btn = document.getElementById('btn-add-subscription');
    if (mode === 'edit') {
        btn.textContent = '保存修改';
        btn.onclick = saveEditedSubscription;
    } else {
        btn.textContent = '添加订阅';
        btn.onclick = addSubscription;
    }
}

let editingSubscriptionUrl = '';

function editSubscription(name, source, interval, url) {
    document.getElementById('subscription-name').value = name || '';
    document.getElementById('subscription-source').value = source || 'remote';
    document.getElementById('subscription-interval').value = interval || 60;
    document.getElementById('subscription-url-input').value = url || '';
    editingSubscriptionUrl = url;
    setSubscriptionFormMode('edit');
    showStatus('正在编辑订阅', 'info');
}

async function saveEditedSubscription() {
    const url = (document.getElementById('subscription-url-input').value || '').trim();
    const name = (document.getElementById('subscription-name').value || '').trim();
    const source = document.getElementById('subscription-source').value;
    const interval = parseInt(document.getElementById('subscription-interval').value, 10);
    if (!url) {
        showStatus('请输入订阅链接', 'warning');
        return;
    }
    setButtonLoading('btn-add-subscription', true, '保存修改', '保存中...');
    try {
        const data = await api('/api/subscriptions', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ original_url: editingSubscriptionUrl, url, name, source, interval })
        });
        showStatus(data.message || '订阅已更新', 'info');
        editingSubscriptionUrl = '';
        clearSubscriptionForm();
        await loadSubscriptions();
        await loadSubscriptionStats();
    } catch (error) {
        showStatus(`修改失败：${error.message}`, 'warning');
    } finally {
        setButtonLoading('btn-add-subscription', false, '保存修改', '保存中...');
    }
}

function clearSubscriptionForm() {
    document.getElementById('subscription-name').value = '';
    document.getElementById('subscription-source').value = 'remote';
    document.getElementById('subscription-interval').value = '60';
    document.getElementById('subscription-url-input').value = '';
    editingSubscriptionUrl = '';
    setSubscriptionFormMode('add');
}

async function addSubscription() {
    const input = document.getElementById('subscription-url-input');
    const url = (input.value || '').trim();
    const name = (document.getElementById('subscription-name').value || '').trim();
    const source = document.getElementById('subscription-source').value;
    const interval = parseInt(document.getElementById('subscription-interval').value, 10);
    if (!url) {
        showStatus('请输入订阅链接', 'warning');
        return;
    }

    setButtonLoading('btn-add-subscription', true, '添加订阅', '添加中...');
    try {
        const data = await api('/api/subscriptions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, name, source, interval })
        });
        showStatus(data.message || '订阅已添加', 'info');
        clearSubscriptionForm();
        await loadSubscriptions();
        await loadSubscriptionStats();
        await loadProxies();
    } catch (error) {
        showStatus(`添加失败：${error.message}`, 'warning');
    } finally {
        setButtonLoading('btn-add-subscription', false, '添加订阅', '添加中...');
    }
}

async function removeSubscription(url) {
    try {
        const data = await api(`/api/subscriptions?url=${encodeURIComponent(url)}`, { method: 'DELETE' });
        showStatus(data.message || '订阅已删除', 'info');
        clearSubscriptionForm();
        await loadSubscriptions();
        await loadSubscriptionStats();
    } catch (error) {
        showStatus(`删除失败：${error.message}`, 'warning');
    }
}

function showHttpHelp() {
    const info = document.getElementById('http-connection-info').textContent;
    alert(`HTTP 代理使用示例:\n\n${info}\n\ncurl -x ${info} https://api.ipify.org`);
}
