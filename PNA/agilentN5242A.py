# Copyright (C) 2012 Ted White
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
name = PNA_X
version = 1.1
description = Talks to the Agilent PNA-X

[startup]
cmdline = %PYTHON% %FILE%
timeout = 30

[shutdown]
message = 987654321
timeout = 30
### END NODE INFO
"""

from labrad import types as T, util
from labrad.server import setting
from labrad.gpib import GPIBManagedServer, GPIBDeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue

from struct import unpack
import time
import numpy

import labrad.units as units
Hz = units.Hz


# the names of the measured parameters
MEAS_PARAM = ['S11', 'S12', 'S21', 'S22']

class PNAWrapper(GPIBDeviceWrapper):
    @inlineCallbacks
    def initialize(self):
        yield self.write('FORM:DATA REAL,64')
        yield self.setupMeasurements(['S21'])

    @inlineCallbacks
    def setupMeasurements(self, desired_meas):
        resp = yield self.query('CALC:PAR:CAT?')
        resp = resp[1:-1].split(',')
        
        defined_par = resp[::2]
        defined_meas = resp[1::2]
        defined_both = zip(defined_par, defined_meas)

        desired_par = [_parName(meas) for meas in desired_meas]
        desired_both = zip(desired_par, desired_meas)
        
        print 'desired:', desired_both
        print 'defined:', defined_both

        deletions = ["CALC:PAR:DEL '%s'" % par \
                     for (par, meas) in defined_both \
                     if meas not in desired_meas]
        additions = ["CALC:PAR:DEF '%s',%s" % (par, meas) \
                     for (par, meas) in desired_both \
                     if par not in defined_par]

        for cmd in deletions + additions:
            print cmd
            yield self.write(cmd)

def _parName(meas):
    return 'labrad_%s' % meas

class AgilentPNAServer(GPIBManagedServer):
    name = 'PNA_X'
    deviceName = ['Agilent Technologies N5242A',
                  'Agilent Technologies N5230A',
                  'Agilent Technologies E8364B',
                  'Agilent Technologies N5232A',
                  'Agilent Technologies N5231A']
    deviceWrapper = PNAWrapper

    def initContext(self, c):
        c['meas'] = ['S21']
        
    @setting(10, bw=['v[Hz]'], returns=['v[Hz]'])
    def bandwidth(self, c, bw=None):
        """Get or set the current bandwidth."""
        dev = self.selectedDevice(c)
        if bw is None:
            resp = yield dev.query('SENS:BAND?')
            bw = T.Value(float(resp), 'Hz')
        elif isinstance(bw, T.Value):
            yield dev.write('SENS:BAND %f' % bw['Hz'])
        returnValue(bw)

    @setting(11, f=['v[Hz]'], returns=['v[Hz]'])
    def frequency(self, c, f=None):
        """Get or set the CW frequency."""
        dev = self.selectedDevice(c)
        if f is None:
            resp = yield dev.query('SENS:FREQ:CW?')
            f = T.Value(float(resp), 'Hz')
        elif isinstance(f, T.Value):
            yield dev.write('SENS:FREQ:CW %f' % f['Hz'])
        returnValue(f)

    @setting(12, fs=['(v[Hz], v[Hz])'], returns=['(v[Hz], v[Hz])'])
    def frequency_range(self, c, fs=None):
        """Get or set the frequency range."""
        dev = self.selectedDevice(c)
        dev.write('SENS:SWE:TYPE LIN')
        if fs is None:
            resp = yield dev.query('SENS:FREQ:STAR?; STOP?')
            fs = tuple(T.Value(float(f), 'Hz') for f in resp.split(';'))
        else:
            yield dev.write('SENS:FREQ:STAR %f; STOP %f' % (fs[0]['Hz'], fs[1]['Hz']))
        returnValue(fs)

    @setting(13, p=['v[dBm]'], returns=['v[dBm]'])
    def power(self, c, p=None):
        """Get or set the power."""
        dev = self.selectedDevice(c)
        if p is None:
            resp = yield dev.query('SOUR:POW?')
            p = T.Value(float(resp), 'dBm')
        elif isinstance(p, T.Value):
            yield dev.write('SOUR:POW %f' % p['dBm'])
        returnValue(p)

    @setting(14, state = '?', returns = 's')
    def powerOnOff(self, c, state=None):
        """Turn on or off a scope channel display.
        State must be in [0,1,'ON','OFF'].
        Channel must be int or string.
        """
        dev = self.selectedDevice(c)
        if state is not None:
            if isinstance(state, str):
                state = state.upper()
            if state not in [0,1,'ON','OFF']:
                raise Exception('state must be 0, 1, "ON", or "OFF"')
            if isinstance(state, int):
                state = str(state)
            yield dev.write('OUTP '+state)
        resp = yield dev.query('OUTP?')
        returnValue(resp)

    @setting(15, ps=['(v[dBm], v[dBm])'], returns=['(v[dBm], v[dBm])'])
    def power_range(self, c, ps=None):
        """Get or set the power range."""
        dev = self.selectedDevice(c)
        dev.write('SENS:SWE:TYPE POW')
        if ps is None:
            resp = yield dev.query('SOUR:POW:STAR?; STOP?')
            ps = tuple(T.Value(float(p), 'dBm') for p in resp.split(';'))
        else:
            good_atten = None
            for attn in [0, 10, 20, 30, 40, 50, 60]:
                if -attn-30 <= ps[0] and -attn+20 >= ps[1]:
                    good_atten = attn
                    break
            if good_atten is None:
                raise Exception('Power out of range.')
            yield dev.write('SOUR:POW:ATT %f; STAR %f; STOP %f' %(good_atten, ps[0]['dBm'], ps[1]['dBm']))
        returnValue(ps)

    @setting(16, n=['w'], returns=['w'])
    def num_points(self, c, n=None):
        """Get or set the number of points."""
        dev = self.selectedDevice(c)
        if n is None:
            resp = yield dev.query('SENS:SWE:POIN?')
            n = long(resp)
        elif isinstance(n, long):
            yield dev.write('SENS:SWE:POIN %u' % n)
        returnValue(n)

    @setting(17, av=['w'], returns=['w'])
    def averages(self, c, av=None):
        """Get or set the number of averages."""
        dev = self.selectedDevice(c)
        if av is None: # if you don't send a number of averages
            resp = yield dev.query('SENS:AVER:COUN?') # it will ask the number of averages set on the PNA
            av = long(resp) # and return that number to you
        elif isinstance(av, long): # if you send in a number
            yield dev.write('SENS:AVER:COUN %u' % av) # sets the averaging number
            yield dev.write('SENS:SWE:GRO:COUN %u' % av) # sets the triggering number
            # yield dev.write('SENS:AVER:MODE SWEEP') # turns average mode to SWEEP
            if av > 1:
                yield dev.write('SENS:AVER ON') # turns averaging on
            else:
                yield dev.write('SENS:AVER OFF') # turns averaging off
        returnValue(av)

    @setting(40, att=['(v[dB], v[dB])'], returns=[''])
    def atten(self, c, att=None):
        """Get or set the x/y attenuation (ignored...)."""
        dev = self.selectedDevice(c)
        
    @setting(123, corr=['v[ns]'], returns=['v[ns]'])
    def electrical_delay(self, c, corr=None):
        """add an electrical delay to cancel the phase difference due to the the cable length"""
        dev = self.selectedDevice(c)
        if corr is None:
            resp = yield dev.query('CALC:CORR:EDEL:TIME?')
            corr = T.Value(float(resp), 'ns')
        elif isinstance(corr, T.Value):
            yield dev.write('CALC:CORR:EDEL:TIME %fNS' % corr)
        returnValue(corr)
        
    @setting(225, bw = ['w'], returns = ['s'])
    def reset_measure(self, c, bw=None):
        """Resets the PNA to trigger continuously with the power on."""
        dev = self.selectedDevice(c)
        if bw == None:
            yield dev.write('SENS:BAND 1000')
        else:
            yield dev.write('SENS:BAND %f' % bw)
        yield dev.write('OUTP 1')
        yield dev.write('INIT:CONT ON')
        returnValue('done')
    
    @setting(129, offs='w', returns='w')
    def phase_offset(self, c, offs = None):
        """add a phase offset to formatted data"""
        dev = self.selectedDevice(c)
        if offs is None:
            resp = yield dev.query('CALC:CORR:OFFS:PHAS?')
            offs = float(resp)
        else:
            yield dev.write('CALC:CORR:OFFS:PHAS %f' % offs)
        returnValue(offs)
        
    @setting(127, offs='w', returns='w')
    def source_phase_offset(self, c, offs = None):
        """add a phase offset to formatted data"""
        dev = self.selectedDevice(c)
        if offs is None:
            resp = yield dev.query('SOUR:PHAS?')
            offs = float(resp)
        else:
            yield dev.write('SOUR:PHAS %f' % offs)
        returnValue(offs)


    @setting(100, log='b', returns='*v[Hz]*2c')
    def freq_sweep(self, c, log=False):
        """Initiate a frequency sweep.

        If log is False (the default), this will perform a
        linear sweep.  If log is True, the sweep will be logarithmic.
        """
        print 'starting'
        dev = self.selectedDevice(c)

        resp = yield dev.query('SENS:FREQ:STAR?; STOP?')
        fstar, fstop = [float(f) for f in resp.split(';')]
        print 'fstar = ',fstar
        print 'fstop = ',fstop
        print resp.split(";")
        sweepType = 'LOG' if log else 'LIN'
        sweeptime, npoints = yield self.startSweep(dev, sweepType)
        if sweeptime > 1:
            sweeptime *= self.sweepFactor(c)
            print "sweeptime = ", sweeptime
            yield util.wakeupCall(sweeptime)

        if log:
            # hack: should use numpy.logspace, but it seems to be broken
            # for now, this works instead.
            lim1, lim2 = numpy.log10(fstar), numpy.log10(fstop)
            freq = 10**numpy.linspace(lim1, lim2, npoints)
        else:
            freq = numpy.linspace(fstar, fstop, npoints)
            
        # wait for sweep to finish
        sparams = yield self.getSweepData(dev, c['meas'])
        returnValue((freq*units.Hz, sparams))

    @setting(102, returns='*v[Hz]*c')
    def get_trace(self, c, trace='S21'):
        """Get a trace.

        Args:
            trace (str): S21, S11, etc.

        Returns:
            (tuple):
                (ValueArray[Hz]): Frequencies.
                (ndarray(complex)): S parameters.
        """
        dev = self.selectedDevice(c)
        resp = yield dev.query('SENS:FREQ:STAR?; STOP?')
        f_start_Hz, f_stop_Hz = (float(f) for f in resp.split(';'))
        n_points = yield dev.query('SENS:SWE:POIN?')
        freq = numpy.linspace(f_start_Hz, f_stop_Hz, n_points) * Hz
        s_params = yield self.getData(dev, trace)
        returnValue((freq, s_params))

    @setting(124, log='b')
    def freq_sweep_phase(self, c, log=False):
        """Initiate a frequency sweep.

        If log is False (the default), this will perform a
        linear sweep.  If log is True, the sweep will be logarithmic.
        """

        dev = self.selectedDevice(c)

        resp = yield dev.query('SENS:FREQ:STAR?; STOP?')
        fstar, fstop = [float(f) for f in resp.split(';')]

        sweepType = 'LOG' if log else 'LIN'
        sweeptime, npoints = yield self.startSweep(dev, sweepType)
        if sweeptime > 1:
            sweeptime *= self.sweepFactor(c)
            # needs factor of 2 since it runs both forward and backward
            yield util.wakeupCall(2*sweeptime)

        if log:
            ## hack: should use numpy.logspace, but it seems to be broken
            ## for now, this works instead.
            lim1, lim2 = numpy.log10(fstar), numpy.log10(fstop)
            freq = 10**numpy.linspace(lim1, lim2, npoints)
        else:
            freq = numpy.linspace(fstar, fstop, npoints)
            
        # wait for sweep to finish
        phase = yield self.getSweepDataPhase(dev, c['meas'])
        returnValue((freq, phase))

    @setting(101, returns='*v[Hz]*2c')
    def power_sweep(self, c):
        """Initiate a power sweep."""
        dev = self.selectedDevice(c)

        resp = yield dev.query('SOUR:POW:STAR?; STOP?')
        pstar, pstop = [float(p) for p in resp.split(';')]

        sweeptime, npoints = yield self.startSweep(dev, 'POW')
        if sweeptime > 1:
            sweeptime *= self.sweepFactor(c)
            yield util.wakeupCall(sweeptime)

        sparams = yield self.getSweepData(dev, c['meas'])

        power = util.linspace(pstar, pstop, npoints)
        power = [T.Value(p, 'dBm') for p in power]
        for s in sparams:
            for i, c in enumerate(s):
                s[i] = T.Complex(c)
        returnValue((power, sparams))
        
    @setting(189)
    def power_sweep_phase(self, c):
        """Initiate a power sweep."""
        dev = self.selectedDevice(c)

        resp = yield dev.query('SOUR:POW:STAR?; STOP?')
        pstar, pstop = [float(p) for p in resp.split(';')]

        sweeptime, npoints = yield self.startSweep(dev, 'POW')
        if sweeptime > 1:
            sweeptime *= self.sweepFactor(c)
            yield util.wakeupCall(sweeptime)
        power = util.linspace(pstar, pstop, npoints)
        power = [T.Value(p, 'dBm') for p in power]
        phase = yield self.getSweepDataPhase(dev, c['meas'])
        returnValue((power, phase))
        
    @setting(111, name=['s'], returns=['*2v'])
    def power_sweep_save(self, c, name='untitled'):
        """Initiate a power sweep.

        The data will be saved to the data vault in the current
        directory for this context.  Note that the default directory
        in the data vault is the root directory, so you should cd
        before trying to save."""
        dev = self.selectedDevice(c)

        resp = yield dev.query('SOUR:POW:STAR?; STOP?')
        pstar, pstop = [float(p) for p in resp.split(';')]

        sweeptime, npoints = yield self.startSweep(dev, 'POW')
        if sweeptime > 1:
            sweeptime *= self.sweepFactor(c)
            yield util.wakeupCall(sweeptime)

        sparams = yield self.getSweepData(dev, c['meas'])

        power = util.linspace(pstar, pstop, npoints)
        power = [T.Value(p, 'dBm') for p in power]
        for s in sparams:
            for i, cplx in enumerate(s):
                s[i] = T.Complex(cplx)

        p = numpy.array(power)
        s = 20*numpy.log10(abs(numpy.array(sparams)))
        phases = numpy.angle(numpy.array(sparams))
        data = numpy.vstack((p, s, phases)).T
        data = data.astype('float64')

        dv = self.client.data_vault
        freq = yield self.frequency(c)
        bw = yield self.bandwidth(c)
        
        independents = ['power [dBm]']
        dependents = [('log mag', Sij, 'dB') for Sij in c['meas']]+[(Sij, 'phase', 'dB') for Sij in c['meas']]
        p = dv.packet()
        p.new(name, independents, dependents)
        p.add(data)
        p.add_comment('Autosaved by PNA server.')
        p.add_parameter('frequency', freq)
        p.add_parameter('bandwidth', bw)
        yield p.send(context=c.ID)
        
        returnValue(data)
        
    @setting(110, name=['s'], returns=['*2v'])
    def freq_sweep_save(self, c, name='untitled'):
        """Initiate a frequency sweep.

        The data will be saved to the data vault in the current
        directory for this context.  Note that the default directory
        in the data vault is the root directory, so you should cd
        before trying to save.
        """
        dev = self.selectedDevice(c)

        resp = yield dev.query('SENS:FREQ:STAR?; STOP?')
        fstar, fstop = [float(f) for f in resp.split(';')]

        sweeptime, npoints = yield self.startSweep(dev, 'LIN')
        if sweeptime > 1:
            sweeptime *= self.sweepFactor(c)
            yield util.wakeupCall(sweeptime)

        sparams = yield self.getSweepData(dev, c['meas'])

        freq = util.linspace(fstar, fstop, npoints)
        freq = [T.Value(f, 'Hz') for f in freq]
        for s in sparams:
            for i, cplx in enumerate(s):
                s[i] = T.Complex(cplx)

        f = numpy.array(freq)
        s = 20*numpy.log10(abs(numpy.array(sparams)))
        phases = numpy.angle(numpy.array(sparams))
        data = numpy.vstack((f, s, phases)).T
        data = data.astype('float64')

        dv = self.client.data_vault
        power = yield self.power(c)
        bw = yield self.bandwidth(c)
        
        independents = ['frequency [Hz]']
        dependents = [(Sij, 'log mag', 'dB') for Sij in c['meas']]+[(Sij, 'phase', 'dB') for Sij in c['meas']]
        p = dv.packet()
        p.new(name, independents, dependents)
        p.add(data)
        p.add_comment('Autosaved by PNA server.')
        p.add_parameter('power', power)
        p.add_parameter('bandwidth', bw)
        yield p.send(context=c.ID)
        
        returnValue(data)

    @setting(200, params=['*s'], returns=['*s'])
    def s_parameters(self, c, params=None):
        """Specify the scattering parameters to be measured.

        The available scattering parameters are:
        'S11', 'S12', 'S21', 'S22'
        """
        dev = self.selectedDevice(c)

        if isinstance(params, list):
            desired = [m.upper() for m in params]
            desired = [m for m in desired if m in MEAS_PARAM]
            
            yield dev.setupMeasurements(desired)
            
            c['meas'] = desired
            
        returnValue(c['meas'])

    # helper methods

    @setting(300, returns='*v[Hz]*2c')
    def cw_measurement(self, c):
        """Initiate a continuous wave measurement.

        """

        dev = self.selectedDevice(c)

        resp = yield dev.query('SENS:FREQ:STAR?; STOP?')
        fstar, fstop = [float(f) for f in resp.split(';')]

        sweeptime, npoints = yield self.startSweep(dev, 'CW')
        if sweeptime > 1:
            sweeptime *= self.sweepFactor(c)
            print sweeptime
            yield util.wakeupCall(sweeptime)    


        time = numpy.linspace(fstar, fstop, npoints)
        
        # wait for sweep to finish
        sparams = yield self.getSweepData(dev, c['meas'])
        returnValue((numpy.append(time, sweeptime), sparams))

    
    
    @inlineCallbacks
    def startSweep(self, dev, sweeptype):
        yield dev.write('SENS:SWE:TIME:AUTO ON; :INIT:CONT ON; :OUTP ON')
        resp = yield dev.query('SENS:SWE:TIME?; POIN?')
        sweeptime, npoints = resp.split(';')
        sweeptime = float(sweeptime)
        npoints = int(npoints)
        yield dev.write('SENS:SWE:TYPE %s' % sweeptype)
        # yield dev.write('ABORT;INIT:IMM')
        resp = yield dev.query('SENS:AVER:COUN?')
        sweeptime *= long(resp)
        yield dev.write('ABORT;SENS:SWE:MODE GRO')
        print 'sweeptime = ',sweeptime
        print 'npoints = ',npoints
        returnValue((sweeptime, npoints))

    @inlineCallbacks
    def getSweepData(self, dev, meas):
        yield dev.query('*OPC?') # wait for sweep to finish
        print 'Query Accepted'
        sdata = yield self.getSParams(dev, meas)    
        yield dev.write('OUTP OFF')
        returnValue(sdata)
        
    @inlineCallbacks
    def getSweepDataPhase(self, dev, meas):
        yield dev.query('*OPC?') # wait for sweep to finish
        sdata = yield self.getPhaseData(dev, meas)
        yield dev.write('OUTP OFF')
        returnValue(sdata)

    @inlineCallbacks
    def getSParams(self, dev, measurements):
        sdata = [(yield self.getData(dev, m)) for m in measurements]
        print 'Got Params'
        returnValue(sdata)
        
    @inlineCallbacks
    def getPhaseData(self, dev, measurements):
        sdata = [(yield self.getFormattedData(dev, m)) for m in measurements]
        returnValue(sdata)

    def sweepFactor(self, c):
        """Multiply the sweeptime by this factor, which
        counts the number of ports that send power.
        """
        ports = set(int(p[-1]) for p in c['meas'])
        return len(ports)

    @inlineCallbacks
    def getData(self, dev, meas):
        """Get binary sweep data from the PNA and parse it.

        The data has the following format:

            1 byte:  '#' (ignored)
            1 byte:  h = header length
            h bytes: d = data length
            d bytes: binary sweep data, as pairs of 64-bit numbers
            1 byte:  <newline> (ignored)

        The 64-bit numbers are unpacked using the struct.unpack
        function from the standard library.
        """
        yield dev.write("CALC:PAR:SEL '%s'" % _parName(meas))
        yield dev.write("CALC:DATA? SDATA")
        # as of pyvisa 1.6 reading a set number of bytes no longer seems to work
        # we still put in a number here because we want to use read_raw to avoid attempted conversion of non-ascii chars
        data = yield dev.read(99999)
        
        # parse header for length of data
        headerLen = long(data[1])        
        dataLen = long(data[2:2+headerLen])
        # parse data
        dataStr = data[2+headerLen:]
        nPoints = dataLen / 16
        
        _parse = lambda s: complex(*unpack('>dd', s))
        data = [_parse(dataStr[16*n:16*(n+1)]) for n in range(nPoints)]
        
        returnValue(data)
        
    @inlineCallbacks
    def getFormattedData(self, dev, meas):
        """Get binary sweep data from the PNA and parse it.

        The data has the following format:

            1 byte:  '#' (ignored)
            1 byte:  h = header length
            h bytes: d = data length
            d bytes: binary sweep data, as pairs of 64-bit numbers
            1 byte:  <newline> (ignored)

        The 64-bit numbers are unpacked using the struct.unpack
        function from the standard library.
        """
        yield dev.write("CALC:PAR:SEL '%s'" % _parName(meas))
        yield dev.write("CALC:FORM PHAS")
        yield dev.write("CALC:DATA? FDATA")
        yield dev.read(bytes=1L) # throw away first byte
        
        headerLen = long((yield dev.read(bytes=1L)))
        dataLen = long((yield dev.read(bytes=headerLen)))

        # read data in chunks
        dataStr = ''
        while len(dataStr) < dataLen:
            chunk = min(10000, dataLen - len(dataStr))
            dataStr += yield dev.read(bytes=long(chunk))
            
        yield dev.read(bytes=1L) # read last byte and discard

        nPoints = dataLen / 8
        
        _parse = lambda s: unpack('>d', s)
        data = [_parse(dataStr[8*n:8*(n+1)]) for n in range(nPoints)]
        
        returnValue(data)


__server__ = AgilentPNAServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
