from hiddifypanel import hutils
from hiddifypanel.models.role import Role
import wtforms as wtf
from flask_wtf import FlaskForm
from flask_bootstrap import SwitchField
from flask_babel import gettext as _
from flask import render_template


from hiddifypanel.models import ConfigEnum, get_hconfigs, BoolConfig, ConfigEnum, hconfig, Proxy
from hiddifypanel.database import db
from wtforms.fields import *
from hiddifypanel.panel import hiddify
from flask_classful import FlaskView
from hiddifypanel.auth import login_required


class ProxyAdmin(FlaskView):
    decorators = [login_required({Role.super_admin})]

    def index(self):
        return render_template('proxy.html', global_config_form=get_global_config_form(), detailed_config_form=get_all_proxy_form())

    def post(self):
        global_config_form = get_global_config_form()
        all_proxy_form = get_all_proxy_form()

        if global_config_form.submit_global.data and global_config_form.validate_on_submit():
            old_configs = get_hconfigs()
            for k, vs in global_config_form.data.items():
                if k in [c for c in ConfigEnum]:
                    BoolConfig.query.filter(BoolConfig.key == k).first().value = vs
                    if vs and k in [ConfigEnum.domain_fronting_http_enable, ConfigEnum.domain_fronting_tls_enable] and hconfig(ConfigEnum.domain_fronting_domain) == "":
                        hutils.flask.flash((_('config.domain-fronting-notsetup-error')), 'danger')

            # print(cat,vs)
            hiddify.get_available_proxies.invalidate_all()
            db.session.commit()
            hiddify.check_need_reset(old_configs)
            all_proxy_form = get_all_proxy_form(True)

        elif all_proxy_form.submit_detail.data and all_proxy_form.validate_on_submit():

            for cdn, vs in all_proxy_form.data.items():  # [c for c in ConfigEnum]:
                if type(vs) is not dict:
                    continue
                for proto, v in vs.items():  # [c for c in ConfigEnum]:
                    if type(v) is not dict:
                        continue
                    for proxy_id, enable in v.items():
                        if not proxy_id.startswith("p_"):
                            continue
                        id = int(proxy_id.split('_')[-1])
                        Proxy.query.filter(Proxy.id == id).first().enable = enable

                # print(cat,vs)
            db.session.commit()
            hiddify.get_available_proxies.invalidate_all()
            hutils.flask.flash_config_success(restart_mode='apply', domain_changed=False)
            # if hconfig(ConfigEnum.parent_panel):
            #     hiddify_api.sync_child_to_parent()
            global_config_form = get_global_config_form(True)
        else:
            hutils.flask.flash((_('config.validation-error')), 'danger')

        return render_template('proxy.html', global_config_form=global_config_form, detailed_config_form=all_proxy_form)

        import flask_babel

        # form=HelloForm()
        # # return render('config.html',form=form)
        # return render_template('config.html',form=HelloForm())
        form = get_config_form()
        return render_template('config.html', form=form)


def get_global_config_form(empty=False):
    boolconfigs = BoolConfig.query.all()

    class DynamicForm(FlaskForm):
        pass

    for cf in boolconfigs:
        if cf.key.apply_mode == 'hidden':
            continue
        if not cf.key.endswith("_enable"):
            continue
        field = SwitchField(_(f'config.{cf.key}.label'), default=cf.value, description=_(f'config.{cf.key}.description'))
        setattr(DynamicForm, f'{cf.key}',  field)
    setattr(DynamicForm, "submit_global", wtf.fields.SubmitField(_('Submit')))
    if empty:
        return DynamicForm(None)
    return DynamicForm()


def get_all_proxy_form(empty=False):
    proxies = hiddify.get_available_proxies(0)
    categories1 = sorted([c for c in {c.cdn: 1 for c in proxies}])

    class DynamicForm(FlaskForm):
        pass

    for cdn in categories1:
        class CDNForm(FlaskForm):
            pass
        cdn_proxies = [c for c in proxies if c.cdn == cdn]
        protos = sorted([c for c in {c.proto: 1 for c in cdn_proxies}])
        for proto in protos:
            class ProtoForm(FlaskForm):
                pass
            proto_proxies = [c for c in cdn_proxies if c.proto == proto]
            for proxy in proto_proxies:
                field = SwitchField(proxy.name, default=proxy.enable, description=f"l3:{proxy.l3} transport:{proxy.transport}")
                setattr(ProtoForm, f"p_{proxy.id}",  field)

            multifield = wtf.fields.FormField(ProtoForm, proto)
            setattr(CDNForm, proto,  multifield)
        field_name = cdn if cdn != "Fake" else _('config.domain_fronting.label')
        multifield = wtf.fields.FormField(CDNForm, field_name)
        setattr(DynamicForm, cdn,  multifield)
    setattr(DynamicForm, "submit_detail", wtf.fields.SubmitField(_('Submit')))
    if empty:
        return DynamicForm(None)
    return DynamicForm()
