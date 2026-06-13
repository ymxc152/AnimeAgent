import type { AutoSubscribeRule, AutoSubscribeRuleCreateRequest } from '../types'
import { useI18n } from '../i18n/useI18n'
import { Button, Input, Switch } from '../components/ui'

interface DiscoveryRuleFormProps {
  ruleForm: AutoSubscribeRuleCreateRequest
  setRuleForm: (form: AutoSubscribeRuleCreateRequest) => void
  editingRule: AutoSubscribeRule | null
  saving: boolean
  onSubmit: (e: React.FormEvent) => void
  onCancel: () => void
}

export function DiscoveryRuleForm({
  ruleForm,
  setRuleForm,
  editingRule,
  saving,
  onSubmit,
  onCancel,
}: DiscoveryRuleFormProps) {
  const { t } = useI18n()

  return (
    <form onSubmit={onSubmit} className="space-y-3 border-t border-slate-100 pt-4 dark:border-slate-800">
      <h4 className="font-medium text-slate-900 dark:text-white">
        {editingRule ? t.discovery.editRule : t.discovery.addRule}
      </h4>
      <Input
        placeholder={t.discovery.ruleName}
        value={ruleForm.name}
        onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })}
        required
      />
      <div className="grid grid-cols-2 gap-3">
        <Input
          placeholder={t.discovery.includeGenres}
          value={ruleForm.include_genres || ''}
          onChange={(e) => setRuleForm({ ...ruleForm, include_genres: e.target.value })}
        />
        <Input
          placeholder={t.discovery.excludeGenres}
          value={ruleForm.exclude_genres || ''}
          onChange={(e) => setRuleForm({ ...ruleForm, exclude_genres: e.target.value })}
        />
        <Input
          placeholder={t.discovery.includeFormats}
          value={ruleForm.include_formats || ''}
          onChange={(e) => setRuleForm({ ...ruleForm, include_formats: e.target.value })}
        />
        <Input
          placeholder={t.discovery.excludeFormats}
          value={ruleForm.exclude_formats || ''}
          onChange={(e) => setRuleForm({ ...ruleForm, exclude_formats: e.target.value })}
        />
        <Input
          placeholder={t.discovery.includeKeywords}
          value={ruleForm.include_keywords || ''}
          onChange={(e) => setRuleForm({ ...ruleForm, include_keywords: e.target.value })}
        />
        <Input
          placeholder={t.discovery.excludeKeywords}
          value={ruleForm.exclude_keywords || ''}
          onChange={(e) => setRuleForm({ ...ruleForm, exclude_keywords: e.target.value })}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input
          type="number"
          step="0.1"
          placeholder={t.discovery.minScore}
          value={ruleForm.min_score ?? ''}
          onChange={(e) => setRuleForm({ ...ruleForm, min_score: e.target.value ? Number(e.target.value) : undefined })}
        />
      </div>
      <div className="flex items-center gap-4">
        <Switch
          checked={ruleForm.use_llm || false}
          onChange={(checked) => setRuleForm({ ...ruleForm, use_llm: checked })}
          label={t.discovery.useLlm}
        />
        <Switch
          checked={ruleForm.enabled || false}
          onChange={(checked) => setRuleForm({ ...ruleForm, enabled: checked })}
          label={t.discovery.ruleEnabled}
        />
      </div>
      <div className="flex justify-end gap-2">
        {editingRule && (
          <Button variant="secondary" onClick={onCancel}>
            {t.common.cancel}
          </Button>
        )}
        <Button type="submit" variant="primary" isLoading={saving}>
          {t.common.save}
        </Button>
      </div>
    </form>
  )
}
