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
            <button class="link" type="button" @click="openDetail(row)">查看详情</button>
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
      <div class="modal-card">
        <div class="modal-head">
          <h3>登记压力容器</h3>
          <button class="link" type="button" @click="closeForm">关闭</button>
        </div>
        <p class="modal-tip">带 * 为必填；其余字段会与必填项一起整条保存，列表与详情读到的是同一份。</p>
        <form @submit.prevent="submitCreate">
          <label v-for="field in formFields" :key="field.name" class="modal-field">
            <span>{{ field.label }}<em v-if="field.required"> *</em></span>
            <input
              v-model="formValues[field.name]"
              :type="field.type ?? 'text'"
              :placeholder="`请输入${field.label}`"
            />
          </label>
          <p v-if="formMessage" class="error-text">{{ formMessage }}</p>
          <div class="modal-actions">
            <button class="btn" type="button" @click="closeForm">取消</button>
            <button class="btn primary" type="submit">保存登记</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal-card">
        <div class="modal-head">
          <h3>压力容器详情</h3>
          <button class="link" type="button" @click="detail = null">关闭</button>
        </div>
        <dl class="detail-grid">
          <div v-for="field in detailFields" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ detail[field] || '—' }}</dd>
          </div>
        </dl>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/vessel'
const columns = ["容器编号", "容器名称", "设计压力", "容积规格", "介质类别", "使用场所", "下次检验日", "容器状态"]
const actions = ["办理投用", "安排检验", "报废容器"]
const statuses = ["待投用", "在用运行", "停用待检", "已报废"]

// 登记表单：必填与选填字段都在这里，提交时整份发给后端，落同一条记录
interface FormField {
  name: string
  label: string
  required?: boolean
  type?: string
}
const formFields: FormField[] = [
  { name: "容器编号", label: "容器编号", required: true },
  { name: "容器名称", label: "容器名称", required: true },
  { name: "设计压力", label: "设计压力", required: true },
  { name: "容积规格", label: "容积规格" },
  { name: "介质类别", label: "介质类别" },
  { name: "使用场所", label: "使用场所" },
  { name: "下次检验日", label: "下次检验日", type: "date" },
]
const detailFields = ["容器编号", "容器名称", "设计压力", "容积规格", "介质类别", "使用场所", "下次检验日", "容器状态"]

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
const formMessage = ref('')
const formValues = reactive<Record<string, string>>(Object.fromEntries(formFields.map((field) => [field.name, ''])))
const detail = ref<Row | null>(null)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  // 打开时只清提示、不清上次填的值：保存没成时原输入仍留在框里
  formMessage.value = ''
  formVisible.value = true
}

function closeForm() {
  formVisible.value = false
  formMessage.value = ''
}

async function submitCreate() {
  formMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...formValues } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      // 后端拒收（缺必填 / 编号重复）时不关闭弹窗，已填的值原样保留
      formMessage.value = payload.message || '压力容器登记未保存，请检查填写内容'
      return
    }
    for (const field of formFields) {
      formValues[field.name] = ''
    }
    formVisible.value = false
    await Promise.all([reload(), reloadStats()])
  } catch (error) {
    formMessage.value = error instanceof Error ? error.message : '压力容器登记未保存，请稍后重试'
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('压力容器详情读取失败')
    }
    // 详情与列表同源：后端按 id 返回的就是列表那条记录
    detail.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '压力容器详情读取失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '压力容器动作未生效，请稍后重试')
    }
    await Promise.all([reload(), reloadStats()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '压力容器操作失败'
  }
}

async function reloadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) {
      return
    }
    const payload = (await response.json()) as Record<string, number>
    stats.value = stats.value.map((item) => ({ ...item, value: payload[item.label] ?? 0 }))
  } catch {
    // 统计取不到时保留上一次的值，不打断列表操作
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
  void reloadStats()
})
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 48px 16px;
  z-index: 20;
}
.modal-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid var(--border);
  width: 520px;
  max-width: 100%;
  padding: 16px 18px;
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.modal-head h3 { margin: 0; font-size: 16px; }
.modal-tip { color: var(--muted); font-size: 12px; margin: 8px 0 12px; }
.modal-field { display: block; margin-bottom: 10px; }
.modal-field span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.modal-field em { color: #b42318; font-style: normal; }
.modal-field input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; margin: 12px 0 0; }
.detail-grid dt { color: var(--muted); font-size: 12px; }
.detail-grid dd { margin: 2px 0 0; font-size: 13px; }
</style>
