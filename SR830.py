# Copyright (C) 2011 Peter O'Malley/Charles Neill
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
### BEGIN NODE INFO
[info]
name = SR830
version = 2.2
description = 

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

from labrad import types as T, gpib
from labrad.server import setting
from labrad.gpib import GPIBManagedServer
from twisted.internet.defer import inlineCallbacks, returnValue

class SR830(GPIBManagedServer):
    name = 'SR830'
    deviceName = 'Stanford_Research_Systems SR830'


    @setting(12, 'Phase', ph=[': query phase offset',  'v[deg]: set phase offset'], returns='v[deg]: phase')
    def phase(self, c, ph = None):
        ''' sets/gets the phase offset '''
        dev = self.selectedDevice(c)
        if ph is None:
            resp = yield dev.query('PHAS?')
            returnValue(float(resp))    	
        else:
            yield dev.write('PHAS ' + str(ph))
            resp = yield dev.query('PHAS?')
            returnValue(float(resp))
            
    @setting(13, 'Reference', ref=[': query reference source', 'b: set external (false) or internal (true) reference source'], returns='b')
    def reference(self, c, ref = None):
        """ sets/gets the reference source. false => external source. true => internal source. """
        dev = self.selectedDevice(c)
        if ref == '':
            resp = yield dev.query('FMOD?')
            returnValue(bool(int(resp)))
        else:
            s = '0'
            if ref:
                s = '1'
            yield dev.write('FMOD ' + s)
            returnValue(ref)   

    @setting(14, 'Frequency', f=[': query frequency', 'v[Hz]: set frequency'], returns='v[Hz]')
    def frequency(self, c, f = None):
        """ Sets/gets the frequency of the internal reference. """
        dev = self.selectedDevice(c)
        if f is None:
            resp = yield dev.query('FREQ?')
            returnValue(float(resp))
        else:
            yield dev.write('FREQ ' + str(f))
            resp = yield dev.query('FREQ?')
            returnValue(float(resp))

    @setting(15, 'External Reference Slope', ers=[': query', 'i: set'], returns='i')
    def external_reference_slope(self, c, ers = None):
        """
        Get/set the external reference slope.
        0 = Sine, 1 = TTL Rising, 2 = TTL Falling
        """
        dev = self.selectedDevice(c)
        if ers is None:
            resp = yield dev.query('RSLP?')
            returnValue(int(resp))
        else:
            yield dev.write('RSLP ' + str(ers))
            returnValue(ers)			

    @setting(16, 'Harmonic', h=[': query harmonic', 'i: set harmonic'], returns='i')
    def harmonic(self, c, h = None):
        """
        Get/set the harmonic.
        Harmonic can be set as high as 19999 but is capped at a frequency of 102kHz.
        """
        dev = self.selectedDevice(c)
        if h is None:
            resp = yield dev.query('HARM?')
            returnValue(int(resp))
        else:
            yield dev.write('HARM ' + str(h))
            returnValue(h)

    @setting(17, 'Sine Out Amplitude', amp=[': query', 'v[V]: set'], returns='v[V]')
    def sine_out_amplitude(self, c, amp = None):
        """ 
        Set/get the amplitude of the sine out.
        Accepts values between .004 and 5.0 V.
        """
        dev = self.selectedDevice(c)
        if amp is None:
            resp = yield dev.query('SLVL?')
            returnValue(float(resp))
        else:
            yield dev.write('SLVL ' + str(amp))
            resp = yield dev.query('SLVL?')
            returnValue(float(resp))

    @setting(18, 'Aux Input', n='i', returns='v[V]')
    def aux_input(self, c, n):
        """Query the value of Aux Input n (1,2,3,4)"""
        dev = self.selectedDevice(c)
        if int(n) < 1 or int(n) > 4:
            raise ValueError("n must be 1,2,3, or 4!")
        resp = yield dev.query('OAUX? ' + str(n))
        returnValue(float(resp))

    @setting(19, 'Aux Output', n='i', v=['v[V]'], returns='v[V]')
    def aux_output(self, c, n, v = None):
        """Get/set the value of Aux Output n (1,2,3,4). v can be from -10.5 to 10.5 V."""
        dev = self.selectedDevice(c)
        if int(n) < 1 or int(n) > 4:
            raise ValueError("n must be 1,2,3, or 4!")
        if v is None:
            resp = yield dev.query('AUXV? ' + str(n))
            returnValue(float(resp))
        else:
            yield dev.write('AUXV ' + str(n) + ', ' + str(v));
            returnValue(v)	

    @setting(21, 'x', returns='v[V]')
    def x(self, c):
        """Query the value of X"""
        dev = self.selectedDevice(c)
        resp = yield dev.query('OUTP? 1')
        returnValue(float(resp))

    @setting(22, 'y', returns='v[V]')
    def y(self, c):
        """Query the value of Y"""
        dev = self.selectedDevice(c)
        resp = yield dev.query('OUTP? 2')
        returnValue(float(resp))

    @setting(23, 'r', returns='v[V]')
    def r(self, c):
        """Query the value of R"""
        dev = self.selectedDevice(c)
        resp = yield dev.query('OUTP? 3')
        returnValue(float(resp))

    @setting(24, 'theta', returns='v[deg]')
    def theta(self, c):
        """Query the value of theta """
        dev = self.selectedDevice(c)
        resp = yield dev.query('OUTP? 4')
        returnValue(float(resp))

    @setting(30, 'Time Constant', i='i', returns='i')
    def time_constant(self, c, i=None):
        """ Set/get the time constant. i=0 --> 10 us; 1-->30us, 2-->100us, 3-->300us, ..., 19 --> 30ks """
        dev = self.selectedDevice(c)
        if i is None:
            resp = yield dev.query("OFLT?")
            returnValue(int(resp))
        else:
            yield dev.write('OFLT ' + str(i))
            returnValue(i)

    @setting(31, 'Sensitivity', i='i', returns='i')
    def sensitivity(self, c, i=None):
        """ Set/get the sensitivity. i=0 --> 2 nV/fA; 1-->5nV/fA, 2-->10nV/fA, 3-->20nV/fA, ..., 26 --> 1V/uA """
        dev = self.selectedDevice(c)
        if i is None:
            resp = yield dev.query("SENS?")
            returnValue(int(resp))
        else:
            yield dev.write('SENS ' + str(i))
            returnValue(i)

    @setting(32, 'Auto Gain')
    def auto_gain(self, c):
        """ Runs the auto gain function. Does nothing if time constant >= 1s. """
        dev = self.selectedDevice(c)
        yield dev.write("AGAN");
        done = False
        resp = yield dev.query("*STB? 1")
        while resp != '0':
            resp = yield dev.query("*STB? 1")
            print "Waiting for auto gain to finish..."

__server__ = SR830()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)