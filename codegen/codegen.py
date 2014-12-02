# -*- Mode: Python -*-

# GDBus - GLib D-Bus Library
#
# Copyright (C) 2008-2011 Red Hat, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General
# Public License along with this library; if not, see <http://www.gnu.org/licenses/>.
#
# Author: David Zeuthen   <davidz@redhat.com>
#  (2014) Jonatan Palsson <jonatan.palsson@pelagicore.com>

import sys

from textwrap import dedent

from . import config
from . import utils
from . import dbustypes

# ----------------------------------------------------------------------------------------------------

class CodeGenerator:
    def __init__(self, ifaces, namespace, interface_prefix, node_xmls, proxy_h, proxy_cpp, stub_cpp, stub_h):
        self.ifaces = ifaces
        self.proxy_h = proxy_h
        self.proxy_cpp = proxy_cpp
        self.stub_h = stub_h
        self.stub_cpp = stub_cpp
        self.node_xmls = node_xmls

    def emit (self, dest, text, newline = True):
        dest.write (text)
        if newline:
            dest.write ("\n")

    def emit_h_p (self, text, newline = True):
        self.emit(self.proxy_h, text, newline)

    def emit_cpp_p (self, text, newline = True):
        self.emit(self.proxy_cpp, text, newline)

    def emit_h_s (self, text, newline = True):
        self.emit(self.stub_h, text, newline)

    def emit_cpp_s (self, text, newline = True):
        self.emit(self.stub_cpp, text, newline)

    def generate_intro(self):
        self.emit_cpp_p(dedent('''/*
                     * Generated by gdbus-codegen-glibmm %s. DO NOT EDIT.
                     *
                     * The license of this code is the same as for the source it was derived from.
                     */
                     ''') %(config.VERSION))

        self.emit_cpp_p('#include "%s"' %(self.proxy_h.name))

    def declare_types(self):
        self.emit_h_p("#include <string>")
        self.emit_h_p("#include <glibmm.h>")
        self.emit_h_p("#include <giomm.h>")
        self.emit_h_p("")

        for i in self.ifaces:
            for ns in i.cpp_namespace_name.split("::")[:-1]:
                self.emit_h_p ("namespace %s {" % ns)
            self.emit_h_p(dedent('''
            class {i.cpp_class_name} : public Glib::ObjectBase {{
            public:
                static void createForBus (Gio::DBus::BusType busType,
                                          Gio::DBus::ProxyFlags proxyFlags,
                                          const std::string &name,
                                          const std::string &objectPath,
                                          const Gio::SlotAsyncReady &slot);

                static Glib::RefPtr<{i.cpp_class_name}> createForBusFinish (Glib::RefPtr<Gio::AsyncResult> result);''').format(**locals()))

            for m in i.methods:
                # Async call method
                self.emit_h_p("    void %s (" % m.name)
                for a in m.in_args:
                    self.emit_h_p("      %s%s," % (a.cpptype_in, a.name))
                self.emit_h_p("      const Gio::SlotAsyncReady &slot);\n")
                self.emit_h_p("")

                # _finish method
                self.emit_h_p("    void %s_finish (" % m.name)
                for a in m.out_args:
                    self.emit_h_p("      %s%s," % (a.cpptype_out, a.name))
                self.emit_h_p("      const Glib::RefPtr<Gio::AsyncResult>& res);")

            for p in i.properties:
                self.emit_h_p("     {p.cpptype_out} {p.name}_get() = 0;".format(**locals()))

            self.emit_h_p("")

            self.emit_h_p(dedent('''
                void reference() {{}}
                void unreference() {{}}
            private:
                {i.cpp_class_name} (Glib::RefPtr<Gio::DBus::Proxy> proxy) : Glib::ObjectBase() {{
                    this->m_proxy = proxy;
                }}
                template<typename T>
                void unwrapList(std::vector<T> &list, const Glib::VariantContainerBase &wrapped) {{
                    for (int i = 0; i < wrapped.get_n_children (); i++) {{
                        Glib::Variant<T> item;
                        wrapped.get_child(item, i);
                        list.push_back(item.get());
                    }}
                }}
                std::vector<Glib::ustring> stdStringVecToGlibStringVec(const std::vector<std::string> &strv) {{
                    std::vector<Glib::ustring> newStrv;
                    for (int i = 0; i < strv.size(); i++) {{
                        newStrv.push_back(strv[i]);
                    }}

                    return newStrv;
                }}
                Glib::RefPtr<Gio::DBus::Proxy> m_proxy;
            }};''').format(**locals()))
            for ns in reversed(i.cpp_namespace_name.split("::")[:-1]):
                self.emit_h_p("}// %s" % ns)

    def generate_method_calls(self, i):
        for m in i.methods:
            # async begin
            self.emit_cpp_p('void %s::%s (' % (i.cpp_namespace_name, m.camel_name))
            for a in m.in_args:
                self.emit_cpp_p('    %sarg_%s,'%(a.cpptype_in, a.name))
            self.emit_cpp_p( '    const Gio::SlotAsyncReady &callback)'
                         '{')

            self.emit_cpp_p("  Glib::VariantContainerBase base;");

            if (len(m.in_args) > 1):
                self.emit_cpp_p("std::vector<Glib::VariantBase> params;")
                for a in m.in_args:
                    self.emit_cpp_p("  " + a.cpptype_send(a.name + "_param", a.name)+ "")
                    self.emit_cpp_p("  params.push_back (%s_param);" % a.name)
            elif (len (m.in_args) == 1):
                for a in m.in_args:
                    self.emit_cpp_p("  " + a.cpptype_send("params", a.name)+ "")

            if (len(m.in_args) > 0):
                self.emit_cpp_p("  base = Glib::VariantContainerBase::create_tuple (params);")

            self.emit_cpp_p('  m_proxy->call (')
            self.emit_cpp_p('    "%s",'%(m.name))

            self.emit_cpp_p('    callback,')
            self.emit_cpp_p('    base);')
            self.emit_cpp_p('}'
                         '')

            # Finish
            self.emit_cpp_p('void %s::%s_finish (' %(i.cpp_namespace_name, m.camel_name))
            for a in m.out_args:
                self.emit_cpp_p('     %sout_%s,'%(a.cpptype_out, a.name))
            self.emit_cpp_p(dedent('''
            const Glib::RefPtr<Gio::AsyncResult>& result)
            {{
              Glib::VariantContainerBase wrapped;
              wrapped = m_proxy->call_finish(result);
            ''').format(**locals()))

            for x in range (0, len(m.out_args)):
                a = m.out_args[x]
                self.emit_cpp_p("  " + a.cppvalue_get (a.name + "_variant", "out_" + a.name, str(x)))
                self.emit_cpp_p("")
            self.emit_cpp_p("}")
            self.emit_cpp_p("")

    def generate_proxy(self, i):
        self.emit_cpp_p(dedent('''
        void {i.cpp_namespace_name}::createForBus (
            Gio::DBus::BusType busType,
            Gio::DBus::ProxyFlags proxyFlags,
            const std::string &name,
            const std::string &objectPath,
            const Gio::SlotAsyncReady &slot) {{
          Gio::DBus::Proxy::create_for_bus (busType,
              name,
              objectPath,
              "{i.name}",
              slot,
              Glib::RefPtr<Gio::DBus::InterfaceInfo>(),
              proxyFlags);
        }}

        Glib::RefPtr<{i.cpp_namespace_name}> {i.cpp_namespace_name}::createForBusFinish (Glib::RefPtr<Gio::AsyncResult> result) {{
            Glib::RefPtr<Gio::DBus::Proxy> proxy = Gio::DBus::Proxy::create_for_bus_finish (result);
            {i.cpp_namespace_name} *p = new {i.cpp_namespace_name} (proxy);
            return Glib::RefPtr<{i.cpp_namespace_name}> (p);
        }}''').format(**locals()))

    def generate_stub_introspection(self):
        for i in range(0, len(self.node_xmls)):
            node_xml = self.node_xmls[i]

            self.emit_h_s ("const char interfaceXml%d[] = { " % i, False)
            for char in node_xml:
                self.emit_h_s ("0x%s, " % char.encode("hex"), False)
            self.emit_h_s("0x00") # Null terminator
            self.emit_h_s ("};")

    def generate_stub_intro(self):
        self.emit_cpp_s ('#include "%s"' % self.stub_h.name)

    def declare_types_stub(self):
        self.emit_h_s(dedent('''
        #include <string>
        #include <glibmm.h>
        #include <giomm.h>
        '''))

        for i in self.ifaces:
            for ns in i.cpp_namespace_name.split("::")[:-1]:
                self.emit_h_s ("namespace %s {" % ns)

            self.emit_h_s("class %s {" % i.cpp_class_name)

            self.emit_h_s("public:")
            self.emit_h_s("%s ();" %i.cpp_class_name)
            self.emit_h_s("void connect (Gio::DBus::BusType, std::string);")

            self.emit_h_s("protected:")
            for m in i.methods:
                # Async call method
                self.emit_h_s("virtual void %s (" % m.name)

                for a in m.in_args:
                    self.emit_h_s("    %s %s," % (a.cpptype_in, a.name))

                self.emit_h_s("    const Glib::RefPtr<Gio::DBus::MethodInvocation>& invocation) = 0;")

            for p in i.properties:
                self.emit_h_s("    virtual {p.cpptype_out} {p.name}_get() = 0;".format(**locals()))

            self.emit_h_s(dedent("""
            void on_bus_acquired(const Glib::RefPtr<Gio::DBus::Connection>& connection,
                                 const Glib::ustring& /* name */);

            void on_name_acquired(const Glib::RefPtr<Gio::DBus::Connection>& /* connection */,
                                  const Glib::ustring& /* name */);

            void on_name_lost(const Glib::RefPtr<Gio::DBus::Connection>& connection,
                              const Glib::ustring& /* name */);

            void on_method_call(const Glib::RefPtr<Gio::DBus::Connection>& /* connection */,
                               const Glib::ustring& /* sender */,
                               const Glib::ustring& /* object_path */,
                               const Glib::ustring& /* interface_name */,
                               const Glib::ustring& method_name,
                               const Glib::VariantContainerBase& parameters,
                               const Glib::RefPtr<Gio::DBus::MethodInvocation>& invocation);

            void on_interface_get_property(Glib::VariantBase& property,
                                                   const Glib::RefPtr<Gio::DBus::Connection>& connection,
                                                   const Glib::ustring& sender,
                                                   const Glib::ustring& object_path,
                                                   const Glib::ustring& interface_name,
                                                   const Glib::ustring& property_name);
            private:
            guint connectionId, registeredId;
            Glib::RefPtr<Gio::DBus::NodeInfo> introspection_data;
            };"""))

            for ns in reversed(i.cpp_namespace_name.split("::")[:-1]):
                self.emit_h_s("}// %s" % ns)

            self.emit_h_s("")

    def define_types_stub(self):
        for i in self.ifaces:
            object_path = "/" + i.name.replace(".", "/")

            self.emit_cpp_s(dedent('''
            {i.cpp_namespace_name}::{i.cpp_class_name} () : connectionId(0), registeredId(0) {{

            }}
            void {i.cpp_namespace_name}::connect (
                Gio::DBus::BusType busType,
                std::string name)
            {{
                try {{
                        introspection_data = Gio::DBus::NodeInfo::create_for_xml(interfaceXml0);
                }} catch(const Glib::Error& ex) {{
                        g_warning("Unable to create introspection data: ");
                        g_warning(std::string(ex.what()).c_str());
                        g_warning("\\n");
                }}
                connectionId = Gio::DBus::own_name(Gio::DBus::BUS_TYPE_SESSION,
                                                   name,
                                                   sigc::mem_fun(this, &{i.cpp_class_name}::on_bus_acquired),
                                                   sigc::mem_fun(this, &{i.cpp_class_name}::on_name_acquired),
                                                   sigc::mem_fun(this, &{i.cpp_class_name}::on_name_lost));
            }}
            void {i.cpp_namespace_name}::on_method_call(const Glib::RefPtr<Gio::DBus::Connection>& /* connection */,
                               const Glib::ustring& /* sender */,
                               const Glib::ustring& /* object_path */,
                               const Glib::ustring& /* interface_name */,
                               const Glib::ustring& method_name,
                               const Glib::VariantContainerBase& parameters,
                               const Glib::RefPtr<Gio::DBus::MethodInvocation>& invocation) {{''').format(**locals()))
            for m in i.methods:
                self.emit_cpp_s("    if (method_name.compare(\"%s\") == 0) {" % m.name)
                for ai in range(len(m.in_args)):
                    a = m.in_args[ai]
                    self.emit_cpp_s("        Glib::Variant<%s> base_%s;" % (a.cpptype_in, a.name))
                    self.emit_cpp_s("        parameters.get_child(base_%s, %d);" % (a.name, ai))
                    self.emit_cpp_s("        %s p_%s;" % (a.cpptype_in, a.name))
                    self.emit_cpp_s("        p_%s = base_%s.get();" % (a.name, a.name))
                    self.emit_cpp_s("")
                self.emit_cpp_s("        %s(" % m.name)
                for a in m.in_args:
                    self.emit_cpp_s("    p_%s," % a.name)
                self.emit_cpp_s("            invocation);")
                self.emit_cpp_s("    }")
            self.emit_cpp_s("    g_print (\"Callback\\n\");")
            self.emit_cpp_s("    }")

            self.emit_cpp_s(dedent('''
            void {i.cpp_namespace_name}::on_interface_get_property(Glib::VariantBase& property,
                                                   const Glib::RefPtr<Gio::DBus::Connection>& connection,
                                                   const Glib::ustring& sender,
                                                   const Glib::ustring& object_path,
                                                   const Glib::ustring& interface_name,
                                                   const Glib::ustring& property_name) {{
            ''').format(**locals()))
            for p in i.properties:
                self.emit_cpp_s(dedent('''
                    if (property_name.compare("{p.name}") == 0) {{
                        property = Glib::Variant<{p.cpptype_out}>::create({p.name}_get());
                    }}
                ''').format(**locals()))
            self.emit_cpp_s(dedent('''
            }}
            void {i.cpp_namespace_name}::on_bus_acquired(const Glib::RefPtr<Gio::DBus::Connection>& connection,
                                     const Glib::ustring& /* name */) {{
                g_print("Bus name acquired!\\n");
                Gio::DBus::InterfaceVTable *interface_vtable =
                      new Gio::DBus::InterfaceVTable(
                            sigc::mem_fun(this, &{i.cpp_class_name}::on_method_call),
                            sigc::mem_fun(this, &{i.cpp_class_name}::on_interface_get_property));
                try {{
                    registeredId = connection->register_object("{object_path}",
                    introspection_data->lookup_interface("{i.name}"),
                    *interface_vtable);
                }}
                catch(const Glib::Error& ex) {{
                    g_warning("Registration of object failed");
                }}

                return;
            }}
            void {i.cpp_namespace_name}::on_name_acquired(const Glib::RefPtr<Gio::DBus::Connection>& /* connection */,
                                  const Glib::ustring& /* name */) {{}}

            void {i.cpp_namespace_name}::on_name_lost(const Glib::RefPtr<Gio::DBus::Connection>& connection,
                              const Glib::ustring& /* name */) {{}}
            ''').format(**locals()))



    def generate(self):
        # Proxy
        self.generate_intro()
        self.declare_types()
        for i in self.ifaces:
            self.generate_method_calls(i)
            self.generate_proxy(i)

        # Stub
        self.generate_stub_introspection()
        self.generate_stub_intro()
        self.declare_types_stub()
        self.define_types_stub()
