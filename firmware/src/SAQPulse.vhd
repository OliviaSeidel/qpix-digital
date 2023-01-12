-------------------------------------------------------------------------------
-- Title      : SAQPulse
-- Project    :
-------------------------------------------------------------------------------
-- File       : SAQPulse.vhd
-- Author     : John Doe  <john@doe.com>
-- Company    :
-- Created    : 2023-01-10
-- Last update: 2023-01-10
-- Platform   :
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: create pulse outputs on Zybo Z7-20 for SAQ and QDB tests.
-- Take a generic input of a pulse width and input clk frequency to generate a
-- list of outputs
-------------------------------------------------------------------------------
-- Copyright (c) 2023
-------------------------------------------------------------------------------
-- Revisions  :
-- Date        Version  Author  Description
-- 2023-01-10  1.0      keefe	Created
-------------------------------------------------------------------------------

library IEEE;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_unsigned.all;

library work;
use work.QpixPkg.all;
use work.QpixProtoPkg.all;

-- fancy sl / slv alias'
use work.UtilityPkg.all;

entity SAQPulse is

  generic (
    INPUT_CLK_F    : integer := 30000000;  -- input clock frequency
    PULSE_WIDTH_us : integer := 10);  -- time in microseconds of expected output pulse
  port (
    clk       : in  std_logic;
    rst       : in  std_logic;
    pulse_frq : in  std_logic_vector(31 downto 0);
    pulse_o   : out std_logic);

end entity SAQPulse;

architecture behavioral of SAQPulse is

  constant RESET_CNT : integer := PULSE_WIDTH_us * INPUT_CLK_F / 1000000;

  signal u_pulse_frq : unsigned(31 downto 0) := (others => '0');

begin  -- architecture behavioral

  u_pulse_frq <= unsigned(pulse_frq);

-- purpose: generate output pulse
-- type   : sequential
-- inputs : clk, rst, u_pulse_frq
-- outputs: pulse_o
pulse_out: process (clk, rst, u_pulse_frq) is

  -- keep track of pulse freq
  variable pulse_frq : unsigned(31 downto 0) := (others => '0');

begin  -- process pulse_out
  if rst = '1' then
    pulse_o <= '0';
    pulse_frq := (others => '0');

  elsif clk'event and clk = '1' then    -- rising clock edge

    -- default for pulse is 'off'
    pulse_frq := pulse_frq +1;
    pulse_o <= '0';

    -- reset count
    if pulse_frq >= u_pulse_frq then
      pulse_frq := (others => '0');
    -- pulse on
    elsif pulse_frq <= RESET_CNT then
      pulse_o <= '1';
    end if;

  end if;
end process pulse_out;



end architecture behavioral;
