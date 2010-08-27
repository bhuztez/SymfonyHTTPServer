#!/usr/bin/env python2

#   SymfonyHTTPServer.py - serve PHP on Symfony for debug
#   Copyright (C) 2010  bhuztez <bhuztez@gmail.com>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.


__all__ = ["SymfonyHTTPRequestHandler"]

from BaseHTTPServer import HTTPServer
from CGIHTTPServer import CGIHTTPRequestHandler, nobody_uid
import CGIHTTPServer
import re
import os
import os.path
import select
from urlparse import urlparse


class SymfonyHTTPRequestHandler(CGIHTTPRequestHandler):

    project_dir = 'www'


    def translate_path(self, path):
        path = self.project_dir + '/' + path
        return CGIHTTPRequestHandler.translate_path(self, path)


    def is_cgi(self):
        if re.search(r'\.\w+$', self.path):
            return False
        else:
            return True

    def _get_script_file(self, scriptname):
        scriptfile = self.translate_path(scriptname)
        
        if not os.path.exists(scriptfile):
            self.send_error(404, "No such CGI script (%r)" % scriptname)
            return
        if not os.path.isfile(scriptfile):
            self.send_error(403, "CGI script is not a plain file (%r)" %
                            scriptname)
            return

        if not (self.have_fork or self.have_popen2 or self.have_popen3):
            self.send_error(403, "CGI script is not a Python script (%r)" %
                            scriptname)
            return
        if not self.is_executable(scriptfile):
            self.send_error(403, "CGI script is not executable (%r)" %
                            scriptname)
            return
        
        return scriptfile

    def _make_env(self, scriptname, scriptfile):
        o = urlparse(self.path)

        env = {}
        env['SERVER_SOFTWARE'] = self.version_string()
        env['SERVER_NAME'] = self.server.server_name
        env['GATEWAY_INTERFACE'] = 'CGI/1.1'
        env['SERVER_PROTOCOL'] = self.protocol_version
        env['SERVER_PORT'] = str(self.server.server_port)
        env['REQUEST_METHOD'] = self.command

        env['PATH_INFO'] = o.path
        # env['PATH_TRANSLATED'] = scriptfile
        # env['SCRIPT_NAME'] = o.path
        
        # http://community.activestate.com/faq/cgi-debugging-no-input-fi
        env['SCRIPT_FILENAME'] = scriptfile
        
        if o.query:
            env['QUERY_STRING'] = o.query
        

        host = self.address_string()
        if host != self.client_address[0]:
            env['REMOTE_HOST'] = host
        env['REMOTE_ADDR'] = self.client_address[0]

        # XXX REMOTE_IDENT
        if self.headers.typeheader is None:
            env['CONTENT_TYPE'] = self.headers.type
        else:
            env['CONTENT_TYPE'] = self.headers.typeheader
        length = self.headers.getheader('content-length')
        if length:
            env['CONTENT_LENGTH'] = length
        referer = self.headers.getheader('referer')
        if referer:
            env['HTTP_REFERER'] = referer
        accept = []
        for line in self.headers.getallmatchingheaders('accept'):
            if line[:1] in "\t\n\r ":
                accept.append(line.strip())
            else:
                accept = accept + line[7:].split(',')
        env['HTTP_ACCEPT'] = ','.join(accept)
        ua = self.headers.getheader('user-agent')
        if ua:
            env['HTTP_USER_AGENT'] = ua
        co = filter(None, self.headers.getheaders('cookie'))
        if co:
            env['HTTP_COOKIE'] = ', '.join(co)
        
        # http://twistedmatrix.com/trac/ticket/4337
        env['REDIRECT_STATUS'] = '200'
        return env


    def run_cgi(self):
        scriptname = 'index.php'
        scriptfile = self._get_script_file(scriptname)
        
        if not scriptfile: return
        
        env = self._make_env(scriptname, scriptfile)

        self.send_response(200, "Script output follows")
               
        # XXX Other HTTP_* headers
        # Since we're setting the env in the parent, provide empty
        # values to override previously set values
        for k in ('QUERY_STRING', 'REMOTE_HOST', 'CONTENT_LENGTH',
                 'HTTP_USER_AGENT', 'HTTP_COOKIE', 'HTTP_REFERER'):
           env.setdefault(k, "")
                
        if self.have_fork:
            # Unix -- fork as we should

            nobody = nobody_uid()
            self.wfile.flush() # Always flush before forking
            pid = os.fork()
            if pid != 0:
                # Parent
                pid, sts = os.waitpid(pid, 0)
                # throw away additional data [see bug #427345]
                if sts:
                    self.log_error("CGI script exit status %#x", sts)
                    
                while select.select([self.rfile], [], [], 0)[0]:
                    if not self.rfile.read(1):
                        break

                return
            # Child
            try:
                try:
                    os.setuid(nobody)
                except os.error:
                    pass
                os.dup2(self.rfile.fileno(), 0)
                os.dup2(self.wfile.fileno(), 1)
                os.execve('/usr/bin/php-cgi', ['php-cgi'], env)
            except:
                self.server.handle_error(self.request, self.client_address)
                os._exit(127)


def test(HandlerClass = SymfonyHTTPRequestHandler, ServerClass = HTTPServer):
    CGIHTTPServer.test(HandlerClass, ServerClass)
    

if __name__ == '__main__':
    test()


