"""ELO stakes and challenge state commit in one progression snapshot."""
import copy
import time
import uuid
from datetime import datetime,timezone
from betting import Book


def adjust(state,uid,amount,reason):
    from progression import rank_for,COUNTERS
    from rank_divisions import thresholds
    p=next((p for p in state['players'].values() if p['discord_id']==int(uid)),None)
    if p is None:raise ValueError('Player progression record unavailable.')
    before,rank=p['points2'],p['rank']
    if before+amount*2<0:raise ValueError('Not enough available ELO for this stake.')
    p['points2']+=amount*2;p['rank']=rank_for(p['points2'],rank,thresholds(p))
    p.setdefault('history',[]).append(dict(at=datetime.now(timezone.utc).isoformat(),kind='Bookies ELO',before=before,after=p['points2'],**{'from':rank,'to':p['rank']},reason=reason))
    if p.get('pending'):p['pending'].update(to=p['rank'],after=p['points2'])
    elif rank!=p['rank']:p['pending']=dict(id=uuid.uuid4().hex,**{'from':rank,'to':p['rank']},before=before,after=p['points2'],delta=dict.fromkeys(COUNTERS,0),reason=reason)


def refund_open(state,reason):
    for b in state.get('elo_betting',{}).get('bets',{}).values():
        if b.get('currency')!='elo' or b['status'] not in ('offered','active'):continue
        for uid in ([b['a'],b['b']] if b['status']=='active' else [b['a']]):adjust(state,uid,b['stake'],reason)
        b.update(status='settled',winner=None,result=reason)


class EloBook(Book):
    def __init__(self,store,ranks):
        self.store,self.ranks=store,ranks
        if 'elo_betting' not in ranks.state:
            legacy=Book(store)
            for b in legacy.data['bets'].values():
                if b['status'] in ('offered','active'):legacy.finish(b,None,'Dollar challenge cancelled and refunded for ELO betting migration.')
            ranks.state['elo_betting']=copy.deepcopy(legacy.data)
            ranks.save()
        self.data=ranks.state['elo_betting']

    def save(self):self.ranks.save()

    def player(self,uid):
        found=self.ranks.find(int(uid))
        if not found:raise ValueError('Both players must link Steam before betting.')
        p=found[1]
        if not p.get('active') or p.get('hold'):raise ValueError('Both players need active, unrestricted ELO profiles.')
        return p

    def wallet(self,uid):
        found=self.ranks.find(int(uid))
        return found[1]['points2']/2 if found else 0

    def offer(self,a,b,stake,mode,target,hours,limit,now):
        if a==b or self.open_for(a) or self.open_for(b):raise ValueError('No self bets; one open challenge per player.')
        if type(stake) is not int or not 10<=stake<=100 or mode not in ('kills','race','limit') or not 1<=hours<=6 or not 1<=target<=1000 or not 0<=limit<=1000:raise ValueError('Stake 10–100 ELO; hours 1–6; valid challenge targets required.')
        self.player(a);self.player(b)
        if self.wallet(a)<stake or self.wallet(b)<stake:raise ValueError('Both players must have enough available ELO to cover the stake.')
        bet=dict(id=uuid.uuid4().hex[:12],a=a,b=b,stake=stake,mode=mode,target=target,hours=hours,limit=limit,status='offered',expires=now+600,result='Awaiting acceptance',currency='elo',season=self.ranks.state.get('season',1))
        adjust(self.ranks.state,a,-stake,'Bookies stake reserved: '+bet['id'])
        self.data['bets'][bet['id']]=bet;self.save();return bet

    def accept(self,b,uid,snapshots,now):
        if b['status']!='offered' or uid!=b['b']:raise ValueError('Only the invited player can accept an open offer.')
        if now>=b['expires']:
            self.finish(b,None,'Offer expired; ELO returned.');raise ValueError('Offer expired.')
        if b.get('season')!=self.ranks.state.get('season',1):raise ValueError('This offer belongs to a closed season.')
        self.player(b['a']);self.player(uid)
        expected={str(b['a']),str(b['b'])} if b['mode']=='race' else {str(b['b'])}
        if set(snapshots)!=expected or any(not 0<=now-s['time']<=300 for s in snapshots.values()):raise ValueError('Fresh starting stats are required for every participant being measured.')
        if self.wallet(uid)<b['stake']:raise ValueError('Not enough available ELO to match the stake.')
        adjust(self.ranks.state,uid,-b['stake'],'Bookies stake matched: '+b['id'])
        b.update(status='active',start=now,end=now+b['hours']*3600,baseline=copy.deepcopy(snapshots),last=copy.deepcopy(snapshots),finals={},result='In progress')
        self.save()

    def finish(self,b,winner,reason):
        if b['status'] not in ('offered','active'):return False
        if b.get('currency')!='elo':raise ValueError('Legacy dollar challenges cannot settle as ELO.')
        if b.get('season')!=self.ranks.state.get('season',1):raise ValueError('Closed-season stakes cannot affect the new season.')
        if winner is not None and winner not in (b['a'],b['b']):raise ValueError('Invalid winner.')
        payouts={b['a']:b['stake']} if b['status']=='offered' else {b['a']:b['stake'],b['b']:b['stake']} if winner is None else {winner:2*b['stake']}
        # Validate all records before mutating either side.
        for uid in payouts:
            if not self.ranks.find(uid):raise ValueError('Progression record missing; settlement retained for review.')
        for uid,amount in payouts.items():adjust(self.ranks.state,uid,amount,'Bookies payout/refund: '+b['id'])
        b.update(status='settled',winner=winner,result=reason)
        self.save();return True

    def reset(self,actor,expected,now):
        if self.data.get('reset_version',0)!=expected:raise ValueError('This reset has already been completed.')
        refund_open(self.ranks.state,'Staff cancelled challenge; ELO stake returned.')
        self.data.setdefault('reset_history',[]).append(dict(actor=actor,at=now,currency='elo'))
        self.data['reset_version']=expected+1;self.save()
