<template>
  <section class="page" data-module="vessel">
    <header class="page-head">
      <div>
        <h2>压力容器管理</h2>
        <p class="page-desc">维护压力容器，围绕容器编号、容器名称、设计压力、容积规格做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记压力容器</button>
        <button class="btn" type="button" @click="exportRows">导出压力容器清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button class="link" type="button" @click="openEdit(row)">修改</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无压力容器数据，可先登记压力容器</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条压力容器记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="formVisible" class="modal-mask" @click.self="closeForm">
      <div class="modal">
        <h3>{{ editingId === null ? '登记压力容器' : '修改压力容器' }}</h3>
        <form @submit.prevent="submitForm">
          <label v-for="field in formFields" :key="field" class="form-item">
            <span>{{ field }}<em v-if="requiredFields.includes(field)" class="req">*</em></span>
            <input
              v-model="form[field]"
              :type="field === '下次检验日' ? 'date' : 'text'"
              :placeholder="`请输入${field}`"
            />
          </label>
          <div v-if="formError" class="form-error">{{ formError }}</div>
          <div class="modal-actions">
            <button class="btn primary" type="submit">保存</button>
            <button class="btn" type="button" @click="closeForm">取消</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="detailVisible" class="modal-mask" @click.self="closeDetail">
      <div class="modal">
        <h3>压力容器详情</h3>
        <dl v-if="detail" class="detail-grid">
          <div v-for="field in detailFields" :key="field" class="detail-item">
            <dt>{{ field }}</dt>
            <dd>{{ detail[field] ?? '—' }}</dd>
          </div>
        </dl>
        <div v-if="!detail" class="form-error">详情读取中…</div>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/vessel'
const columns = ["容器编号", "容器名称", "设计压力", "容积规格", "介质类别", "使用场所", "下次检验日", "容器状态"]
const actions = ["办理投用", "安排检验", "报废容器"]
const formFields = ["容器编号", "容器名称", "设计压力", "容积规格", "介质类别", "使用场所", "下次检验日"]
const requiredFields = ["容器编号", "容器名称", "设计压力"]
const detailFields = ["容器编号", "容器名称", "设计压力", "容积规格", "介质类别", "使用场所", "下次检验日", "容器状态", "status"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const stats = ref([
  { label: "在册台数", value: 0 },
  { label: "在用容器", value: 0 },
  { label: "停用待检", value: 0 },
  { label: "超期未检", value: 0 },
])

const formVisible = ref(false)
const form = ref<Record<string, string>>({})
const formError = ref('')
const editingId = ref<number | null>(null)

const detailVisible = ref(false)
const detail = ref<Row | null>(null)

function emptyForm(): Record<string, string> {
  return Object.fromEntries(formFields.map((field) => [field, '']))
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  editingId.value = null
  form.value = emptyForm()
  formError.value = ''
  formVisible.value = true
}

function openEdit(row: Row) {
  editingId.value = typeof row.id === 'number' ? row.id : Number(row.id)
  form.value = emptyForm()
  for (const field of formFields) {
    const value = row[field]
    form.value[field] = value === null || value === undefined ? '' : String(value)
  }
  formError.value = ''
  formVisible.value = true
}

function closeForm() {
  formVisible.value = false
  form.value = emptyForm()
  formError.value = ''
  editingId.value = null
}

async function submitForm() {
  formError.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...form.value } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      // 没存成：表单原值留住，只说明理由，不关闭弹窗
      formError.value = payload.message || '压力容器未保存成功，请核对后重试'
      return
    }
    closeForm()
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '压力容器保存失败'
  }
}

async function openDetail(row: Row) {
  detailVisible.value = true
  detail.value = null
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('压力容器详情读取失败')
    }
    detail.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '压力容器详情读取失败'
    closeDetail()
  }
}

function closeDetail() {
  detailVisible.value = false
  detail.value = null
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) {
      return
    }
    const payload = (await response.json()) as Record<string, number>
    stats.value = [
      { label: '在册台数', value: payload['在册台数'] ?? 0 },
      { label: '在用容器', value: payload['在用容器'] ?? 0 },
      { label: '停用待检', value: payload['停用待检'] ?? 0 },
      { label: '超期未检', value: payload['超期未检'] ?? 0 },
    ]
  } catch {
    // 统计读取失败不阻塞列表
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '压力容器动作未生效，请稍后重试')
    }
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '压力容器操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('压力容器列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '压力容器列表读取失败'
  }
}

onMounted(() => {
  void reload()
  void loadStats()
})
</script>

<style scoped>
.page-actions { display: flex; gap: 8px; }
.modal-mask {
  position: fixed; inset: 0; background: rgba(16, 24, 40, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.modal {
  background: #fff; border-radius: 10px; padding: 18px 20px; width: 560px;
  max-width: calc(100vw - 32px); max-height: calc(100vh - 64px); overflow: auto;
}
.modal h3 { margin: 0 0 14px; font-size: 16px; }
.form-item { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }
.form-item span { font-size: 13px; color: var(--muted); }
.form-item .req { color: #b42318; font-style: normal; margin-left: 2px; }
.form-item input {
  border: 1px solid var(--border); border-radius: 6px; padding: 7px 9px; font-size: 13px;
}
.form-error {
  color: #b42318; font-size: 13px; background: #fef3f2; border: 1px solid #fecdca;
  border-radius: 6px; padding: 8px 10px; margin-bottom: 10px;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 6px; }
.detail-grid {
  display: grid; grid-template-columns: 120px 1fr; gap: 6px 12px; margin: 0 0 14px;
}
.detail-item { display: contents; }
.detail-item dt { color: var(--muted); font-size: 13px; }
.detail-item dd { margin: 0; font-size: 13px; }
</style>
