-- Atomic AI-token debit. Run once in the Supabase SQL editor.
-- Replaces the read-then-write pattern in the backend, which allowed
-- double-spends under concurrent requests.
--
-- Returns the new balance on success, or -1 when the balance is insufficient.

create or replace function public.debit_tokens(p_user_id uuid, p_cost int)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
  new_balance int;
begin
  update profiles
     set ai_token_balance = ai_token_balance - p_cost
   where id = p_user_id
     and ai_token_balance >= p_cost
  returning ai_token_balance into new_balance;

  if new_balance is null then
    return -1;
  end if;

  return new_balance;
end;
$$;

-- Only the backend (service role) may call this; block direct client calls.
revoke execute on function public.debit_tokens(uuid, int) from anon, authenticated;
grant execute on function public.debit_tokens(uuid, int) to service_role;
